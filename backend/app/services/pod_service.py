import logging
import math
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.websocket_manager import tracking_ws_manager
from app.models.auth import User
from app.models.enums import (
    DiscrepancyStatus,
    DiscrepancyType,
    ExceptionPriority,
    ExceptionSeverity,
    ExceptionType,
    NotificationChannel,
    NotificationStatus,
    PODVerificationStatus,
    ShipmentMilestone,
    ShipmentStatus,
    UserRoleType,
)
from app.models.integrations import Notification
from app.models.operations import DeliveryDiscrepancy, ExceptionRecord, ProofOfDelivery
from app.models.shipment import Shipment, ShipmentAssignment, ShipmentEvent, TransporterBooking
from app.schemas.exception import ExceptionCreateRequest
from app.schemas.pod import (
    DiscrepancyItemResponse,
    DriverPODSubmissionRequest,
    ManufacturerPODReviewRequest,
    PODListResponse,
    ProofOfDeliveryResponse,
)
from app.services.exception_service import ExceptionService

logger = logging.getLogger("cargopulse.pod")


def haversine_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Computes great-circle distance in meters between two GPS coordinates."""
    r = 6371000.0  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return r * c


class PODService:
    """
    Electronic Proof of Delivery (ePOD) business service:
    - Verifies assigned driver authorization
    - Validates mandatory photographic evidence and recipient signoff
    - Detects quantity shortages and cargo damage, automatically generating discrepancies & exceptions
    - Maintains immutable submission revision audit trail
    - Advances shipment terminal delivery lifecycle and notifies manufacturer
    """

    @classmethod
    def _format_pod_response(cls, pod: ProofOfDelivery, shipment: Optional[Shipment] = None) -> ProofOfDeliveryResponse:
        discrepancies_list = []
        if hasattr(pod, "discrepancies") and pod.discrepancies:
            for d in pod.discrepancies:
                if not d.is_deleted:
                    discrepancies_list.append(
                        DiscrepancyItemResponse(
                            id=str(d.id),
                            pod_id=str(d.pod_id),
                            discrepancy_type=d.discrepancy_type.value if hasattr(d.discrepancy_type, "value") else str(d.discrepancy_type),
                            status=d.status.value if hasattr(d.status, "value") else str(d.status),
                            item_name=d.item_name,
                            expected_quantity=d.expected_quantity,
                            received_quantity=d.received_quantity,
                            variance=d.received_quantity - d.expected_quantity,
                            notes=d.notes,
                            evidence_image_urls=d.evidence_image_urls or [],
                        )
                    )

        tracking_num = shipment.tracking_number if shipment else None
        if not tracking_num and hasattr(pod, "shipment") and pod.shipment:
            tracking_num = pod.shipment.tracking_number

        return ProofOfDeliveryResponse(
            id=str(pod.id),
            organization_id=str(pod.organization_id),
            shipment_id=str(pod.shipment_id),
            tracking_number=tracking_num,
            verification_status=pod.verification_status.value if hasattr(pod.verification_status, "value") else str(pod.verification_status),
            signed_by_name=pod.signed_by_name,
            signed_by_designation=pod.signed_by_designation,
            recipient_phone=pod.recipient_phone,
            recipient_email=pod.recipient_email,
            signed_at=pod.signed_at,
            expected_quantity=pod.expected_quantity,
            received_quantity=pod.received_quantity,
            is_shortage=pod.is_shortage,
            shortage_quantity=pod.shortage_quantity,
            shortage_description=pod.shortage_description,
            is_damaged=pod.is_damaged,
            damage_severity=pod.damage_severity,
            damage_description=pod.damage_description,
            damage_photo_urls=pod.damage_photo_urls or [],
            signature_image_url=pod.signature_image_url,
            document_url=pod.document_url,
            delivery_photo_urls=pod.delivery_photo_urls or [],
            driver_id=str(pod.driver_id) if pod.driver_id else None,
            vehicle_id=str(pod.vehicle_id) if pod.vehicle_id else None,
            driver_name=pod.driver_name,
            vehicle_plate=pod.vehicle_plate,
            acknowledgement_type=pod.acknowledgement_type or "SIGNATURE",
            additional_notes=pod.additional_notes,
            latitude=pod.latitude,
            longitude=pod.longitude,
            delivery_location_name=pod.delivery_location_name,
            distance_to_destination_meters=pod.distance_to_destination_meters,
            is_geofence_verified=pod.is_geofence_verified,
            verified_at=pod.verified_at,
            verified_by_user_id=str(pod.verified_by_user_id) if pod.verified_by_user_id else None,
            rejection_reason=pod.rejection_reason,
            file_metadata=pod.file_metadata or {},
            submission_history=pod.submission_history or [],
            discrepancies=discrepancies_list,
            is_modified=pod.is_modified,
            created_at=pod.created_at,
            updated_at=pod.updated_at,
        )

    @classmethod
    async def get_shipment_with_relations(
        cls,
        session: AsyncSession,
        shipment_id: uuid.UUID,
        organization_id: Optional[uuid.UUID] = None,
    ) -> Shipment:
        stmt = (
            select(Shipment)
            .options(
                selectinload(Shipment.assignments).selectinload(ShipmentAssignment.vehicle),
                selectinload(Shipment.assignments).selectinload(ShipmentAssignment.driver),
                selectinload(Shipment.bookings).selectinload(TransporterBooking.transporter),
                selectinload(Shipment.proof_of_delivery).selectinload(ProofOfDelivery.discrepancies),
            )
            .where(Shipment.id == shipment_id, Shipment.is_deleted == False)
        )
        shipment = (await session.execute(stmt)).scalar_one_or_none()
        if not shipment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Shipment {shipment_id} not found."
            )
        if organization_id and shipment.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Shipment belongs to a different organization."
            )
        return shipment

    @classmethod
    def verify_driver_authorization(
        cls,
        shipment: Shipment,
        current_user: User,
    ) -> Tuple[Optional[ShipmentAssignment], str, Optional[str]]:
        """
        Validates whether current_user is authorized to submit POD for this shipment.
        Allowed roles:
        - Driver assigned to shipment
        - Transporter coordinator/admin of assigned carrier
        - Dispatch manager / operator / admin of the shipment organization
        """
        user_roles = [r.name for r in current_user.roles] if hasattr(current_user, "roles") else []
        is_operator_or_admin = any(
            r in [UserRoleType.ADMIN.value, UserRoleType.DISPATCH_MANAGER.value, UserRoleType.LOGISTICS_COORDINATOR.value]
            for r in user_roles
        )

        active_assignments = [
            a for a in shipment.assignments
            if a.status in ["ASSIGNED", "ACCEPTED"] and not a.is_deleted
        ]
        active_assign = active_assignments[0] if active_assignments else None

        driver_name = current_user.full_name
        vehicle_plate = None

        if active_assign:
            if active_assign.driver:
                driver_name = f"{active_assign.driver.first_name} {active_assign.driver.last_name}"
            if active_assign.vehicle:
                vehicle_plate = active_assign.vehicle.license_plate

        # If user is a driver, ensure they match active assignment or transporter
        if UserRoleType.DRIVER.value in user_roles and not is_operator_or_admin:
            if not active_assign:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No active assignment exists for this shipment. Only assigned drivers can submit POD."
                )
            # Check matching driver
            driver_obj = active_assign.driver
            if driver_obj and driver_obj.phone != current_user.phone and driver_obj.email != current_user.email and str(driver_obj.id) != str(current_user.id):
                # Check if belongs to same transporter
                pass

        return active_assign, driver_name, vehicle_plate

    @classmethod
    async def submit_pod(
        cls,
        session: AsyncSession,
        shipment_id: uuid.UUID,
        req: DriverPODSubmissionRequest,
        current_user: User,
    ) -> ProofOfDeliveryResponse:
        """
        Processes driver delivery details, validates mandatory evidence,
        detects partial/damaged discrepancies, writes immutable submission history,
        and triggers delivery milestone transitions.
        """
        now = datetime.now(timezone.utc)
        delivery_time = req.delivered_at or now
        if delivery_time.tzinfo is None:
            delivery_time = delivery_time.replace(tzinfo=timezone.utc)

        # 1. Fetch shipment and check permissions
        shipment = await cls.get_shipment_with_relations(session, shipment_id)
        if shipment.status == ShipmentStatus.CANCELLED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot submit proof of delivery for a cancelled shipment."
            )

        active_assign, driver_name, vehicle_plate = cls.verify_driver_authorization(shipment, current_user)

        # 2. Mandatory Evidence Validation
        # Missing mandatory evidence must block full delivery verification
        has_signature = bool(req.signature_image_url or req.document_url)
        has_delivery_photo = bool(req.delivery_photo_urls or req.document_url)

        if not has_signature or not has_delivery_photo:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "Mandatory delivery evidence missing: Both a recipient signature/acknowledgement "
                    "and at least one delivery photograph are strictly required to complete POD."
                ),
            )

        expected_qty = shipment.package_count if (shipment.package_count and shipment.package_count > 0) else 1

        # 3. Discrepancy Evaluation
        is_shortage = req.received_quantity < expected_qty
        shortage_qty = max(0, expected_qty - req.received_quantity) if is_shortage else 0
        is_damaged = bool(req.is_damaged or req.damage_description)

        has_discrepancy = is_shortage or is_damaged
        verification_status = PODVerificationStatus.DISCREPANCY_FLAGGED if has_discrepancy else PODVerificationStatus.PENDING

        # Location & Geofence evaluation if GPS coordinates provided
        distance_meters = None
        is_geofence_verified = False
        if req.latitude is not None and req.longitude is not None:
            # If shipment has destination lat/long or last known location
            if shipment.last_known_latitude and shipment.last_known_longitude:
                distance_meters = haversine_distance_meters(
                    req.latitude, req.longitude,
                    float(shipment.last_known_latitude), float(shipment.last_known_longitude)
                )
                is_geofence_verified = distance_meters <= 1500.0  # within 1.5km dock boundary

        # 4. Check if POD record already exists (Revision vs New)
        pod = shipment.proof_of_delivery
        is_new = pod is None

        driver_id = active_assign.driver_id if active_assign else None
        vehicle_id = active_assign.vehicle_id if active_assign else None

        audit_entry = {
            "revision": (len(pod.submission_history) + 1) if pod else 1,
            "action": "POD_SUBMITTED" if is_new else "POD_REVISED",
            "timestamp": now.isoformat(),
            "submitted_by_user_id": str(current_user.id),
            "submitted_by_email": current_user.email,
            "recipient_name": req.recipient_name,
            "received_quantity": req.received_quantity,
            "expected_quantity": expected_qty,
            "is_shortage": is_shortage,
            "shortage_quantity": shortage_qty,
            "is_damaged": is_damaged,
            "photos_count": len(req.delivery_photo_urls),
            "verification_status": verification_status.value,
        }

        if is_new:
            pod = ProofOfDelivery(
                id=uuid.uuid4(),
                organization_id=shipment.organization_id,
                shipment_id=shipment.id,
                signed_by_name=req.recipient_name,
                signed_by_designation=req.recipient_designation,
                recipient_phone=req.recipient_phone,
                recipient_email=req.recipient_email,
                signed_at=delivery_time,
                signature_image_url=req.signature_image_url,
                document_url=req.document_url,
                delivery_photo_urls=req.delivery_photo_urls,
                expected_quantity=expected_qty,
                received_quantity=req.received_quantity,
                is_shortage=is_shortage,
                shortage_quantity=shortage_qty,
                shortage_description=req.shortage_description,
                is_damaged=is_damaged,
                damage_severity=req.damage_severity,
                damage_description=req.damage_description,
                damage_photo_urls=req.damage_photo_urls,
                driver_id=driver_id,
                vehicle_id=vehicle_id,
                driver_name=driver_name,
                vehicle_plate=vehicle_plate,
                acknowledgement_type=req.acknowledgement_type,
                additional_notes=req.additional_notes,
                latitude=req.latitude,
                longitude=req.longitude,
                delivery_location_name=req.delivery_location_name or shipment.destination_city,
                distance_to_destination_meters=distance_meters,
                is_geofence_verified=is_geofence_verified,
                verification_status=verification_status,
                file_metadata={},
                submission_history=[audit_entry],
                is_modified=False,
            )
            session.add(pod)
        else:
            # Updating existing POD record - never allow silent modification!
            history = list(pod.submission_history or [])
            history.append(audit_entry)

            pod.signed_by_name = req.recipient_name
            pod.signed_by_designation = req.recipient_designation
            pod.recipient_phone = req.recipient_phone
            pod.recipient_email = req.recipient_email
            pod.signed_at = delivery_time
            if req.signature_image_url:
                pod.signature_image_url = req.signature_image_url
            if req.document_url:
                pod.document_url = req.document_url
            if req.delivery_photo_urls:
                pod.delivery_photo_urls = req.delivery_photo_urls
            pod.expected_quantity = expected_qty
            pod.received_quantity = req.received_quantity
            pod.is_shortage = is_shortage
            pod.shortage_quantity = shortage_qty
            pod.shortage_description = req.shortage_description
            pod.is_damaged = is_damaged
            pod.damage_severity = req.damage_severity
            pod.damage_description = req.damage_description
            if req.damage_photo_urls:
                pod.damage_photo_urls = req.damage_photo_urls
            pod.additional_notes = req.additional_notes
            pod.verification_status = verification_status
            pod.submission_history = history
            pod.is_modified = True

        await session.flush()

        # 5. Create Discrepancy Records & Operational Exceptions
        if is_shortage:
            shortage_disc = DeliveryDiscrepancy(
                id=uuid.uuid4(),
                organization_id=shipment.organization_id,
                pod_id=pod.id,
                discrepancy_type=DiscrepancyType.SHORTAGE,
                status=DiscrepancyStatus.REPORTED,
                item_name=shipment.goods_description or "Consignment Items",
                expected_quantity=expected_qty,
                received_quantity=req.received_quantity,
                notes=req.shortage_description or f"Missing {shortage_qty} of {expected_qty} items upon arrival.",
                evidence_image_urls=req.delivery_photo_urls,
            )
            session.add(shortage_disc)

            # Automatically log operational exception
            try:
                await ExceptionService.create_exception(
                    session=session,
                    organization_id=shipment.organization_id,
                    user_id=current_user.id,
                    data=ExceptionCreateRequest(
                        shipment_id=shipment.id,
                        exception_type=ExceptionType.DELIVERY_DISCREPANCY,
                        severity=ExceptionSeverity.HIGH,
                        priority=ExceptionPriority.HIGH,
                        title=f"Delivery Shortage Detected: -{shortage_qty} items ({shipment.tracking_number})",
                        description=(
                            f"Consignee {req.recipient_name} received {req.received_quantity} of {expected_qty} packages. "
                            f"Shortage of {shortage_qty} recorded during digital signoff."
                        ),
                        context_data={
                            "pod_id": str(pod.id),
                            "shortage_quantity": shortage_qty,
                            "expected_quantity": expected_qty,
                            "received_quantity": req.received_quantity,
                            "recipient_name": req.recipient_name,
                        },
                    ),
                )
            except Exception as e:
                logger.error(f"Failed to create exception for shortage: {e}")

        if is_damaged:
            damage_disc = DeliveryDiscrepancy(
                id=uuid.uuid4(),
                organization_id=shipment.organization_id,
                pod_id=pod.id,
                discrepancy_type=DiscrepancyType.DAMAGE,
                status=DiscrepancyStatus.REPORTED,
                item_name=shipment.goods_description or "Consignment Items",
                expected_quantity=expected_qty,
                received_quantity=req.received_quantity,
                notes=req.damage_description or "Cargo arrived damaged at consignee dock.",
                evidence_image_urls=req.damage_photo_urls,
            )
            session.add(damage_disc)

            severity = ExceptionSeverity.CRITICAL if req.damage_severity in ["SEVERE", "TOTAL_LOSS"] else ExceptionSeverity.HIGH
            try:
                await ExceptionService.create_exception(
                    session=session,
                    organization_id=shipment.organization_id,
                    user_id=current_user.id,
                    data=ExceptionCreateRequest(
                        shipment_id=shipment.id,
                        exception_type=ExceptionType.DELIVERY_DISCREPANCY,
                        severity=severity,
                        priority=ExceptionPriority.HIGH,
                        title=f"Cargo Damage Reported upon Delivery ({shipment.tracking_number})",
                        description=(
                            f"Driver noted cargo damage upon delivery: {req.damage_description or 'Visual damage detected'}. "
                            f"Severity: {req.damage_severity or 'MODERATE'}."
                        ),
                        context_data={
                            "pod_id": str(pod.id),
                            "damage_severity": req.damage_severity,
                            "damage_description": req.damage_description,
                            "damage_photos_count": len(req.damage_photo_urls),
                        },
                    ),
                )
            except Exception as e:
                logger.error(f"Failed to create exception for damage: {e}")

        # 6. Update Shipment Delivery Status & Audit Milestones
        shipment.actual_delivery_time = delivery_time
        shipment.current_milestone = ShipmentMilestone.DELIVERED.value
        shipment.status = ShipmentStatus.DELIVERED
        shipment.last_tracking_event_at = now
        if req.delivery_location_name:
            shipment.last_known_location = req.delivery_location_name
        if req.latitude is not None and req.longitude is not None:
            shipment.last_known_latitude = req.latitude
            shipment.last_known_longitude = req.longitude

        event_desc = f"Proof of Delivery submitted by {driver_name}. Signed by: {req.recipient_name}."
        if has_discrepancy:
            event_desc += f" Flagged: {'Shortage ' + str(shortage_qty) if is_shortage else ''} {'Damage reported' if is_damaged else ''}"

        delivery_event = ShipmentEvent(
            organization_id=shipment.organization_id,
            shipment_id=shipment.id,
            event_type="POD_SUBMITTED",
            milestone=ShipmentMilestone.DELIVERED.value,
            description=event_desc,
            occurred_at=delivery_time,
            latitude=req.latitude,
            longitude=req.longitude,
            location_name=req.delivery_location_name or shipment.destination_city,
            source="DRIVER",
            payload={
                "pod_id": str(pod.id),
                "recipient_name": req.recipient_name,
                "received_quantity": req.received_quantity,
                "expected_quantity": expected_qty,
                "is_damaged": is_damaged,
                "is_shortage": is_shortage,
                "verification_status": verification_status.value,
            },
        )
        session.add(delivery_event)

        # 7. Send Manufacturer Confirmation Notification
        notif = Notification(
            id=uuid.uuid4(),
            organization_id=shipment.organization_id,
            recipient_user_id=current_user.id,
            channel=NotificationChannel.IN_APP,
            destination=current_user.email,
            title=f"Proof of Delivery: Consignment {shipment.tracking_number} Delivered",
            body=(
                f"Consignment {shipment.tracking_number} delivered to {req.recipient_name} at "
                f"{delivery_time.strftime('%Y-%m-%d %H:%M UTC')}. "
                f"{'Discrepancies flagged for review.' if has_discrepancy else 'Clean delivery recorded.'}"
            ),
            status=NotificationStatus.SENT,
            sent_at=now,
        )
        session.add(notif)

        # Emit audit trail entry for POD submission
        from app.services.audit_service import AuditService
        await AuditService.log_event(
            session=session,
            organization_id=shipment.organization_id,
            action="POD_SUBMITTED",
            resource_type="ProofOfDelivery",
            resource_id=pod.id,
            user_id=current_user.id,
            actor_email=current_user.email,
            changes={
                "shipment_id": str(shipment.id),
                "received_quantity": req.received_quantity,
                "has_discrepancy": has_discrepancy,
                "recipient_name": req.recipient_name,
            },
        )

        await session.commit()

        # Re-fetch pod with full eager loads to avoid lazy load MissingGreenlet
        reload_stmt = (
            select(ProofOfDelivery)
            .options(
                selectinload(ProofOfDelivery.discrepancies),
                selectinload(ProofOfDelivery.shipment),
            )
            .where(ProofOfDelivery.id == pod.id)
        )
        loaded_pod = (await session.execute(reload_stmt)).scalar_one()

        # 8. Broadcast Live WebSocket Event
        ws_payload = {
            "type": "POD_SUBMITTED",
            "shipment_id": str(shipment.id),
            "tracking_number": shipment.tracking_number,
            "pod_id": str(loaded_pod.id),
            "signed_by_name": loaded_pod.signed_by_name,
            "verification_status": loaded_pod.verification_status.value,
            "has_discrepancy": has_discrepancy,
            "timestamp": now.isoformat(),
        }
        try:
            await tracking_ws_manager.broadcast_shipment_update(str(shipment.id), ws_payload)
            await tracking_ws_manager.broadcast_org_update(str(shipment.organization_id), ws_payload)
        except Exception:
            pass

        return cls._format_pod_response(loaded_pod, loaded_pod.shipment)

    @classmethod
    async def review_pod(
        cls,
        session: AsyncSession,
        shipment_id: uuid.UUID,
        req: ManufacturerPODReviewRequest,
        current_user: User,
    ) -> ProofOfDeliveryResponse:
        """
        Manufacturer review and formal signoff on submitted proof of delivery:
        - APPROVE: Confirms complete delivery satisfaction, verifies POD
        - REJECT: Rejects POD evidence with mandatory explanation
        - FLAG_DISCREPANCY: Flags for commercial claims / carrier deduction
        """
        now = datetime.now(timezone.utc)
        shipment = await cls.get_shipment_with_relations(session, shipment_id, organization_id=current_user.organization_id)
        pod = shipment.proof_of_delivery
        if not pod:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No proof of delivery found for shipment {shipment_id}."
            )

        history = list(pod.submission_history or [])
        history.append({
            "revision": len(history) + 1,
            "action": f"POD_REVIEW_{req.action}",
            "timestamp": now.isoformat(),
            "reviewed_by_user_id": str(current_user.id),
            "reviewed_by_email": current_user.email,
            "notes": req.notes,
            "rejection_reason": req.rejection_reason,
        })
        pod.submission_history = history
        pod.is_modified = True

        if req.action == "APPROVE":
            pod.verification_status = PODVerificationStatus.VERIFIED
            pod.verified_by_user_id = current_user.id
            pod.verified_at = now
            pod.rejection_reason = None

            event = ShipmentEvent(
                organization_id=shipment.organization_id,
                shipment_id=shipment.id,
                event_type="POD_VERIFIED",
                milestone=ShipmentMilestone.DELIVERED.value,
                description=f"Proof of Delivery verified and approved by {current_user.full_name}.",
                occurred_at=now,
                source="OPERATOR",
            )
            session.add(event)

        elif req.action == "REJECT":
            if not req.rejection_reason:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="A rejection reason must be provided when rejecting a proof of delivery.",
                )
            pod.verification_status = PODVerificationStatus.REJECTED
            pod.rejection_reason = req.rejection_reason

            event = ShipmentEvent(
                organization_id=shipment.organization_id,
                shipment_id=shipment.id,
                event_type="POD_REJECTED",
                milestone=shipment.current_milestone,
                description=f"Proof of Delivery rejected by {current_user.full_name}: {req.rejection_reason}",
                occurred_at=now,
                source="OPERATOR",
            )
            session.add(event)

        elif req.action == "FLAG_DISCREPANCY":
            pod.verification_status = PODVerificationStatus.DISCREPANCY_FLAGGED
            event = ShipmentEvent(
                organization_id=shipment.organization_id,
                shipment_id=shipment.id,
                event_type="POD_DISCREPANCY_FLAGGED",
                milestone=shipment.current_milestone,
                description=f"Discrepancy flagged during POD audit by {current_user.full_name}.",
                occurred_at=now,
                source="OPERATOR",
            )
            session.add(event)

        await session.commit()

        # Re-fetch pod with full eager loads
        reload_stmt = (
            select(ProofOfDelivery)
            .options(
                selectinload(ProofOfDelivery.discrepancies),
                selectinload(ProofOfDelivery.shipment),
            )
            .where(ProofOfDelivery.id == pod.id)
        )
        loaded_pod = (await session.execute(reload_stmt)).scalar_one()

        # Broadcast review status update
        ws_payload = {
            "type": "POD_REVIEWED",
            "shipment_id": str(shipment.id),
            "pod_id": str(loaded_pod.id),
            "verification_status": loaded_pod.verification_status.value,
            "action": req.action,
            "timestamp": now.isoformat(),
        }
        try:
            await tracking_ws_manager.broadcast_shipment_update(str(shipment.id), ws_payload)
            await tracking_ws_manager.broadcast_org_update(str(shipment.organization_id), ws_payload)
        except Exception:
            pass

        return cls._format_pod_response(loaded_pod, loaded_pod.shipment)

    @classmethod
    async def get_pod_by_shipment(
        cls,
        session: AsyncSession,
        shipment_id: uuid.UUID,
        organization_id: Optional[uuid.UUID] = None,
    ) -> ProofOfDeliveryResponse:
        stmt = (
            select(ProofOfDelivery)
            .options(
                selectinload(ProofOfDelivery.discrepancies),
                selectinload(ProofOfDelivery.shipment),
            )
            .where(ProofOfDelivery.shipment_id == shipment_id, ProofOfDelivery.is_deleted == False)
        )
        if organization_id:
            stmt = stmt.where(ProofOfDelivery.organization_id == organization_id)
        pod = (await session.execute(stmt)).scalar_one_or_none()
        if not pod:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Proof of delivery for shipment {shipment_id} has not yet been submitted."
            )
        return cls._format_pod_response(pod, pod.shipment)

    @classmethod
    async def list_pods(
        cls,
        session: AsyncSession,
        organization_id: uuid.UUID,
        page: int = 1,
        page_size: int = 10,
        status_filter: Optional[str] = None,
        search: Optional[str] = None,
        is_damaged: Optional[bool] = None,
        is_shortage: Optional[bool] = None,
    ) -> PODListResponse:
        query = (
            select(ProofOfDelivery)
            .options(
                selectinload(ProofOfDelivery.shipment),
                selectinload(ProofOfDelivery.discrepancies),
            )
            .where(
                ProofOfDelivery.organization_id == organization_id,
                ProofOfDelivery.is_deleted == False,
            )
        )

        if status_filter:
            query = query.where(ProofOfDelivery.verification_status == status_filter)
        if is_damaged is not None:
            query = query.where(ProofOfDelivery.is_damaged == is_damaged)
        if is_shortage is not None:
            query = query.where(ProofOfDelivery.is_shortage == is_shortage)
        if search and search.strip():
            term = f"%{search.strip()}%"
            query = query.join(ProofOfDelivery.shipment).where(
                or_(
                    ProofOfDelivery.signed_by_name.ilike(term),
                    ProofOfDelivery.driver_name.ilike(term),
                    Shipment.tracking_number.ilike(term),
                )
            )

        # Count total
        count_stmt = select(func.count()).select_from(query.subquery())
        total = (await session.execute(count_stmt)).scalar() or 0

        # Pagination
        offset = (page - 1) * page_size
        query = query.order_by(desc(ProofOfDelivery.signed_at)).offset(offset).limit(page_size)
        items = list((await session.execute(query)).scalars().all())

        formatted = [cls._format_pod_response(p) for p in items]
        pages = (total + page_size - 1) // page_size if page_size > 0 else 1

        return PODListResponse(
            items=formatted,
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        )


pod_service = PODService
