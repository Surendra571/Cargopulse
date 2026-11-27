import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy import func, select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.websocket_manager import tracking_ws_manager
from app.models.auth import User
from app.models.enums import (
    ExceptionPriority,
    ExceptionSeverity,
    ExceptionType,
    ShipmentMilestone,
    ShipmentStatus,
    TrackingEventSource,
    UserRoleType,
)
from app.models.operations import ExceptionRecord
from app.models.shipment import (
    Shipment,
    ShipmentAssignment,
    ShipmentEvent,
    TransporterBooking,
)
from app.schemas.exception import ExceptionCreateRequest
from app.schemas.tracking import (
    MilestoneProgressItem,
    ShipmentLocationSummary,
    ShipmentTimelineResponse,
    TrackingEventCreateRequest,
    TrackingEventResponse,
    TrackingScanResponse,
    UpdateETARequest,
)
from app.services.exception_service import ExceptionService

logger = logging.getLogger("cargopulse.tracking")

# Canonical order and progression rank for the 10 Milestones
MILESTONE_PROGRESSION: Dict[str, int] = {
    ShipmentMilestone.SHIPMENT_CREATED.value: 1,
    ShipmentMilestone.TRANSPORTER_ASSIGNED.value: 2,
    ShipmentMilestone.BOOKING_CONFIRMED.value: 3,
    ShipmentMilestone.VEHICLE_ASSIGNED.value: 4,
    ShipmentMilestone.VEHICLE_ARRIVED.value: 5,
    ShipmentMilestone.PICKUP_COMPLETED.value: 6,
    ShipmentMilestone.IN_TRANSIT.value: 7,
    ShipmentMilestone.CHECKPOINT_REACHED.value: 7,  # Checkpoints occur within IN_TRANSIT
    ShipmentMilestone.OUT_FOR_DELIVERY.value: 8,
    ShipmentMilestone.DELIVERED.value: 9,
}

# Milestone to ShipmentStatus mapping
MILESTONE_STATUS_MAP: Dict[str, ShipmentStatus] = {
    ShipmentMilestone.SHIPMENT_CREATED.value: ShipmentStatus.DRAFT,
    ShipmentMilestone.TRANSPORTER_ASSIGNED.value: ShipmentStatus.COMMITTED,
    ShipmentMilestone.BOOKING_CONFIRMED.value: ShipmentStatus.COMMITTED,
    ShipmentMilestone.VEHICLE_ASSIGNED.value: ShipmentStatus.COMMITTED,
    ShipmentMilestone.VEHICLE_ARRIVED.value: ShipmentStatus.AT_PICKUP,
    ShipmentMilestone.PICKUP_COMPLETED.value: ShipmentStatus.DISPATCHED,
    ShipmentMilestone.IN_TRANSIT.value: ShipmentStatus.IN_TRANSIT,
    ShipmentMilestone.CHECKPOINT_REACHED.value: ShipmentStatus.IN_TRANSIT,
    ShipmentMilestone.OUT_FOR_DELIVERY.value: ShipmentStatus.OUT_FOR_DELIVERY,
    ShipmentMilestone.DELIVERED.value: ShipmentStatus.DELIVERED,
}

ALL_MILESTONES = [
    (ShipmentMilestone.SHIPMENT_CREATED.value, "Shipment Created"),
    (ShipmentMilestone.TRANSPORTER_ASSIGNED.value, "Transporter Assigned"),
    (ShipmentMilestone.BOOKING_CONFIRMED.value, "Booking Confirmed"),
    (ShipmentMilestone.VEHICLE_ASSIGNED.value, "Vehicle Assigned"),
    (ShipmentMilestone.VEHICLE_ARRIVED.value, "Vehicle Arrived at Dock"),
    (ShipmentMilestone.PICKUP_COMPLETED.value, "Pickup Completed & Loaded"),
    (ShipmentMilestone.IN_TRANSIT.value, "In Transit"),
    (ShipmentMilestone.CHECKPOINT_REACHED.value, "Route Checkpoint Reached"),
    (ShipmentMilestone.OUT_FOR_DELIVERY.value, "Out for Delivery"),
    (ShipmentMilestone.DELIVERED.value, "Consignment Delivered"),
]


class TrackingService:
    """
    Centralized business service for real-time shipment milestone progression,
    telematics event recording, out-of-order event handling, and stale tracking detection.
    """

    async def get_shipment_or_404(
        self,
        session: AsyncSession,
        shipment_id: uuid.UUID,
        current_user: Optional[User] = None,
        organization_id: Optional[uuid.UUID] = None,
    ) -> Shipment:
        stmt = (
            select(Shipment)
            .options(
                selectinload(Shipment.events),
                selectinload(Shipment.assignments).selectinload(ShipmentAssignment.vehicle),
                selectinload(Shipment.assignments).selectinload(ShipmentAssignment.driver),
                selectinload(Shipment.bookings).selectinload(TransporterBooking.transporter),
            )
            .where(Shipment.id == shipment_id)
        )
        res = await session.execute(stmt)
        shipment = res.scalar_one_or_none()

        if not shipment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Shipment {shipment_id} not found."
            )

        # Enforce tenant isolation if organization_id or current_user provided
        expected_org_id = organization_id or (current_user.organization_id if current_user else None)
        if expected_org_id and shipment.organization_id != expected_org_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Shipment belongs to a different organization."
            )

        # Enforce transporter / driver assignment permissions if caller is carrier/driver
        if current_user:
            user_roles = [r.name for r in current_user.roles] if hasattr(current_user, "roles") else []
            is_carrier = any(r in [UserRoleType.CARRIER.value, UserRoleType.TRANSPORTER_ADMIN.value, UserRoleType.TRANSPORTER_COORDINATOR.value] for r in user_roles)
            is_driver = UserRoleType.DRIVER.value in user_roles

            if is_carrier or is_driver:
                active_assignments = [
                    a for a in shipment.assignments
                    if a.status in ["ASSIGNED", "ACCEPTED"] and not a.is_deleted
                ]
                assigned_driver_ids = [a.driver_id for a in active_assignments if a.driver_id]
                assigned_transporter_ids = [
                    b.transporter_id for b in shipment.bookings
                    if b.status in ["CONFIRMED", "ACCEPTED"] and not b.is_deleted
                ]

                if is_driver and current_user.id not in assigned_driver_ids and not is_carrier:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Driver not assigned to this shipment."
                    )

        return shipment

    async def record_tracking_event(
        self,
        session: AsyncSession,
        shipment_id: uuid.UUID,
        req: TrackingEventCreateRequest,
        current_user: Optional[User] = None,
        source_override: Optional[TrackingEventSource] = None,
        organization_id: Optional[uuid.UUID] = None,
    ) -> ShipmentEvent:
        shipment = await self.get_shipment_or_404(
            session=session,
            shipment_id=shipment_id,
            current_user=current_user,
            organization_id=organization_id,
        )

        now_utc = datetime.now(timezone.utc)
        occurred_at = req.occurred_at or now_utc
        if occurred_at.tzinfo is None:
            occurred_at = occurred_at.replace(tzinfo=timezone.utc)

        # 1. Check Cancellation and Terminal States
        if shipment.status == ShipmentStatus.CANCELLED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot record tracking events on a cancelled shipment."
            )

        milestone_str = req.milestone.value if req.milestone else None
        event_type = req.event_type or milestone_str or "TRACKING_UPDATE"

        # If shipment is already delivered, cannot transition to an earlier status
        if shipment.status == ShipmentStatus.DELIVERED and milestone_str != ShipmentMilestone.DELIVERED.value:
            if milestone_str and MILESTONE_PROGRESSION.get(milestone_str, 0) < MILESTONE_PROGRESSION.get(ShipmentMilestone.DELIVERED.value, 9):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Shipment has already reached DELIVERED terminal status. Cannot transition to previous milestone."
                )

        # 2. Duplicate Event Prevention (Idempotency Key & Tight Window Hash)
        if req.idempotency_key:
            stmt = select(ShipmentEvent).where(
                ShipmentEvent.shipment_id == shipment.id,
                ShipmentEvent.idempotency_key == req.idempotency_key,
            )
            existing = (await session.execute(stmt)).scalar_one_or_none()
            if existing:
                logger.info(f"Idempotent event match for key {req.idempotency_key}; returning existing event.")
                return existing
        else:
            # Check duplicate within 60-second window for exact same event_type and close coordinates
            window_start = occurred_at - timedelta(seconds=60)
            window_end = occurred_at + timedelta(seconds=60)
            stmt = select(ShipmentEvent).where(
                ShipmentEvent.shipment_id == shipment.id,
                ShipmentEvent.event_type == event_type,
                ShipmentEvent.occurred_at >= window_start,
                ShipmentEvent.occurred_at <= window_end,
            )
            existing = (await session.execute(stmt)).scalars().first()
            if existing:
                logger.info(f"Duplicate tracking event detected within 60s for {shipment.id} {event_type}; deduplicating.")
                return existing

        # 3. Determine Event Source
        source = (
            source_override.value
            if source_override
            else req.source.value
            if req.source
            else "SYSTEM"
        )
        if current_user and not source_override and not req.source:
            user_roles = [r.name for r in current_user.roles] if hasattr(current_user, "roles") else []
            if UserRoleType.DRIVER.value in user_roles:
                source = TrackingEventSource.DRIVER.value
            elif any(r in [UserRoleType.CARRIER.value, UserRoleType.TRANSPORTER_ADMIN.value, UserRoleType.TRANSPORTER_COORDINATOR.value] for r in user_roles):
                source = TrackingEventSource.TRANSPORTER.value
            else:
                source = TrackingEventSource.OPERATOR.value

        # 4. Out-of-order handling & State Progression
        current_rank = MILESTONE_PROGRESSION.get(shipment.current_milestone or "", 0)
        new_rank = MILESTONE_PROGRESSION.get(milestone_str or "", 0)

        # Advance milestone and status if valid forward progression or newer timestamp
        latest_time = shipment.last_tracking_event_at
        is_newer_than_latest = latest_time is None or occurred_at >= latest_time

        if milestone_str and (new_rank > current_rank or (new_rank == current_rank and is_newer_than_latest)):
            shipment.current_milestone = milestone_str
            if milestone_str in MILESTONE_STATUS_MAP:
                shipment.status = MILESTONE_STATUS_MAP[milestone_str]

            if milestone_str == ShipmentMilestone.PICKUP_COMPLETED.value:
                shipment.actual_pickup_time = occurred_at
            elif milestone_str == ShipmentMilestone.DELIVERED.value:
                shipment.actual_delivery_time = occurred_at
        elif milestone_str:
            logger.info(
                f"Out-of-order or historical milestone '{milestone_str}' received for shipment {shipment.id} "
                f"(current: {shipment.current_milestone}). Preserving history without status regression."
            )

        # 5. Location and Telematics Updates
        if req.location_name:
            shipment.last_known_location = req.location_name
        if req.latitude is not None and req.longitude is not None:
            shipment.last_known_latitude = req.latitude
            shipment.last_known_longitude = req.longitude

        shipment.last_tracking_event_at = (
            max(latest_time, occurred_at) if latest_time else occurred_at
        )

        # Reset stale flag on any valid update
        shipment.is_tracking_stale = False

        # 6. ETA Update and Significant Delay Detection
        if req.estimated_delivery_at:
            new_eta = req.estimated_delivery_at
            if new_eta.tzinfo is None:
                new_eta = new_eta.replace(tzinfo=timezone.utc)

            original_eta = shipment.expected_delivery_time
            if original_eta.tzinfo is None:
                original_eta = original_eta.replace(tzinfo=timezone.utc)

            shipment.expected_delivery_time = new_eta
            shipment.eta_updated_at = now_utc

            delay_delta = new_eta - original_eta
            delay_minutes = int(delay_delta.total_seconds() // 60)
            shipment.eta_delay_minutes = max(0, delay_minutes)

            # Trigger automated exception if delay exceeds 60 minutes
            if delay_minutes >= 60:
                logger.warning(f"Significant delay ({delay_minutes} min) detected on shipment {shipment.id}")
                try:
                    await ExceptionService.create_exception(
                        session=session,
                        organization_id=shipment.organization_id,
                        user_id=None,
                        data=ExceptionCreateRequest(
                            shipment_id=shipment.id,
                            exception_type=ExceptionType.DELIVERY_DELAYED,
                            severity=ExceptionSeverity.HIGH,
                            priority=ExceptionPriority.HIGH,
                            title=f"Significant Delivery Delay: +{delay_minutes}m ({shipment.tracking_number})",
                            description=(
                                f"Shipment {shipment.tracking_number} ETA revised to "
                                f"{new_eta.strftime('%Y-%m-%d %H:%M UTC')}. "
                                f"Delay of {delay_minutes} minutes exceeds the 60-minute SLA buffer."
                            ),
                            context_data={
                                "original_eta": original_eta.isoformat(),
                                "revised_eta": new_eta.isoformat(),
                                "delay_minutes": delay_minutes,
                                "source": source,
                                "last_location": shipment.last_known_location,
                            },
                        ),
                    )
                except Exception as exc_err:
                    logger.error(f"Failed to record automatic delay exception: {exc_err}")

        # 7. Create Append-Only ShipmentEvent Record
        description = req.description or f"Milestone event: {milestone_str or event_type}"
        event = ShipmentEvent(
            organization_id=shipment.organization_id,
            shipment_id=shipment.id,
            event_type=event_type,
            milestone=milestone_str,
            description=description,
            occurred_at=occurred_at,
            latitude=req.latitude,
            longitude=req.longitude,
            location_name=req.location_name,
            source=source,
            idempotency_key=req.idempotency_key,
            estimated_delivery_at=req.estimated_delivery_at,
            created_by_user_id=current_user.id if current_user else None,
            payload=req.payload or {},
        )
        session.add(event)

        # Audit Trail Recording
        from app.services.audit_service import AuditService
        raw_event_type = req.event_type.value if hasattr(req.event_type, "value") else str(event_type)
        audit_action = f"MILESTONE_{raw_event_type}"
        if raw_event_type == "PICKUP_COMPLETED":
            audit_action = "PICKUP_CONFIRMED"
        elif raw_event_type == "DELIVERED":
            audit_action = "DELIVERY_CONFIRMED"

        status_str = shipment.status.value if hasattr(shipment.status, "value") else str(shipment.status)

        await AuditService.log_event(
            session=session,
            organization_id=shipment.organization_id,
            action=audit_action,
            resource_type="Shipment",
            resource_id=shipment.id,
            user_id=current_user.id if current_user else None,
            actor_email=current_user.email if current_user else None,
            changes={
                "event_type": raw_event_type,
                "current_milestone": shipment.current_milestone,
                "shipment_status": status_str,
                "location": req.location_name,
            },
        )

        await session.commit()
        await session.refresh(event)

        # 8. Real-time WebSocket Broadcast
        event_data = {
            "type": "TRACKING_EVENT_RECORDED",
            "shipment_id": str(shipment.id),
            "tracking_number": shipment.tracking_number,
            "status": shipment.status.value,
            "current_milestone": shipment.current_milestone,
            "event": {
                "id": str(event.id),
                "event_type": event.event_type,
                "milestone": event.milestone,
                "description": event.description,
                "occurred_at": event.occurred_at.isoformat(),
                "location_name": event.location_name,
                "latitude": event.latitude,
                "longitude": event.longitude,
                "source": event.source,
                "estimated_delivery_at": event.estimated_delivery_at.isoformat() if event.estimated_delivery_at else None,
            },
            "expected_delivery_time": shipment.expected_delivery_time.isoformat(),
            "eta_delay_minutes": shipment.eta_delay_minutes,
            "is_tracking_stale": shipment.is_tracking_stale,
        }

        try:
            await tracking_ws_manager.broadcast_shipment_update(str(shipment.id), event_data)
            await tracking_ws_manager.broadcast_org_update(str(shipment.organization_id), event_data)
        except Exception as ws_err:
            logger.warning(f"WebSocket broadcast error: {ws_err}")

        return event

    async def get_shipment_timeline(
        self,
        session: AsyncSession,
        shipment_id: uuid.UUID,
        current_user: Optional[User] = None,
        organization_id: Optional[uuid.UUID] = None,
    ) -> ShipmentTimelineResponse:
        shipment = await self.get_shipment_or_404(
            session=session,
            shipment_id=shipment_id,
            current_user=current_user,
            organization_id=organization_id,
        )

        # Load events ordered chronologically
        events_stmt = (
            select(ShipmentEvent)
            .where(ShipmentEvent.shipment_id == shipment.id)
            .order_by(ShipmentEvent.occurred_at.asc())
        )
        events = list((await session.execute(events_stmt)).scalars().all())

        # Build chronological milestones roadmap
        milestone_events_map: Dict[str, ShipmentEvent] = {}
        for ev in events:
            if ev.milestone and ev.milestone not in milestone_events_map:
                milestone_events_map[ev.milestone] = ev

        current_milestone = shipment.current_milestone
        current_rank = MILESTONE_PROGRESSION.get(current_milestone or "", 0)

        progress_items: List[MilestoneProgressItem] = []
        for ms_key, ms_label in ALL_MILESTONES:
            ms_rank = MILESTONE_PROGRESSION.get(ms_key, 0)
            ev = milestone_events_map.get(ms_key)
            is_completed = (ev is not None) or (current_rank >= ms_rank and current_rank > 0)
            progress_items.append(
                MilestoneProgressItem(
                    milestone=ms_key,
                    label=ms_label,
                    completed=is_completed,
                    occurred_at=ev.occurred_at if ev else None,
                    location_name=ev.location_name if ev else None,
                    is_current=(ms_key == current_milestone),
                )
            )

        # Resolve active transporter & vehicle/driver summary
        transporter_info = None
        vehicle_info = None
        driver_info = None

        if shipment.bookings:
            confirmed_bkg = next(
                (b for b in shipment.bookings if b.status in ["CONFIRMED", "ACCEPTED"] and not b.is_deleted),
                shipment.bookings[0] if shipment.bookings else None,
            )
            if confirmed_bkg and confirmed_bkg.transporter:
                transporter_info = {
                    "id": str(confirmed_bkg.transporter.id),
                    "name": confirmed_bkg.transporter.name,
                    "code": confirmed_bkg.transporter.code,
                    "phone": confirmed_bkg.transporter.primary_phone,
                }

        if shipment.assignments:
            active_assign = next(
                (a for a in shipment.assignments if a.status in ["ASSIGNED", "ACCEPTED"] and not a.is_deleted),
                shipment.assignments[0] if shipment.assignments else None,
            )
            if active_assign:
                if active_assign.vehicle:
                    vehicle_info = {
                        "id": str(active_assign.vehicle.id),
                        "license_plate": active_assign.vehicle.license_plate,
                        "vehicle_type": active_assign.vehicle.vehicle_type,
                    }
                if active_assign.driver:
                    driver_info = {
                        "id": str(active_assign.driver.id),
                        "name": f"{active_assign.driver.first_name} {active_assign.driver.last_name}",
                        "phone": active_assign.driver.phone,
                    }

        return ShipmentTimelineResponse(
            shipment_id=shipment.id,
            tracking_number=shipment.tracking_number,
            status=shipment.status.value,
            current_milestone=shipment.current_milestone,
            scheduled_pickup_time=shipment.scheduled_pickup_time,
            actual_pickup_time=shipment.actual_pickup_time,
            expected_delivery_time=shipment.expected_delivery_time,
            actual_delivery_time=shipment.actual_delivery_time,
            is_tracking_stale=shipment.is_tracking_stale,
            last_tracking_event_at=shipment.last_tracking_event_at,
            last_known_location=shipment.last_known_location,
            last_known_latitude=shipment.last_known_latitude,
            last_known_longitude=shipment.last_known_longitude,
            eta_delay_minutes=shipment.eta_delay_minutes,
            total_weight_kg=float(shipment.total_weight_kg),
            goods_description=shipment.goods_description,
            origin=ShipmentLocationSummary(
                name=shipment.origin_name,
                city=shipment.origin_city,
                state=shipment.origin_state,
                postal_code=shipment.origin_postal_code,
                dock_number=shipment.origin_dock_number,
                contact_name=shipment.origin_contact_name,
                contact_phone=shipment.origin_contact_phone,
            ),
            destination=ShipmentLocationSummary(
                name=shipment.destination_name,
                city=shipment.destination_city,
                state=shipment.destination_state,
                postal_code=shipment.destination_postal_code,
                dock_number=shipment.destination_dock_number,
                contact_name=shipment.destination_contact_name,
                contact_phone=shipment.destination_contact_phone,
            ),
            transporter=transporter_info,
            assigned_vehicle=vehicle_info,
            assigned_driver=driver_info,
            events=[TrackingEventResponse.model_validate(e) for e in events],
            milestone_progress=progress_items,
        )

    async def update_eta(
        self,
        session: AsyncSession,
        shipment_id: uuid.UUID,
        req: UpdateETARequest,
        current_user: Optional[User] = None,
    ) -> ShipmentEvent:
        shipment = await self.get_shipment_or_404(
            session=session,
            shipment_id=shipment_id,
            current_user=current_user,
        )

        create_req = TrackingEventCreateRequest(
            event_type="ETA_REVISED",
            milestone=ShipmentMilestone(shipment.current_milestone) if shipment.current_milestone in [m.value for m in ShipmentMilestone] else None,
            description=req.reason or f"Expected delivery time updated to {req.new_eta.strftime('%Y-%m-%d %H:%M UTC')}",
            estimated_delivery_at=req.new_eta,
            location_name=req.location_name,
            latitude=req.latitude,
            longitude=req.longitude,
            source=req.source or TrackingEventSource.OPERATOR,
            payload={"reason": req.reason, "updated_by": current_user.email if current_user else "SYSTEM"},
        )
        return await self.record_tracking_event(
            session=session,
            shipment_id=shipment_id,
            req=create_req,
            current_user=current_user,
        )

    async def scan_stale_tracking(
        self,
        session: AsyncSession,
        organization_id: Optional[uuid.UUID] = None,
        threshold_hours: int = 6,
        simulated_now: Optional[datetime] = None,
    ) -> TrackingScanResponse:
        now_utc = simulated_now or datetime.now(timezone.utc)
        stale_cutoff = now_utc - timedelta(hours=threshold_hours)

        active_statuses = [
            ShipmentStatus.COMMITTED,
            ShipmentStatus.AT_PICKUP,
            ShipmentStatus.DISPATCHED,
            ShipmentStatus.IN_TRANSIT,
            ShipmentStatus.OUT_FOR_DELIVERY,
        ]

        query = select(Shipment).where(
            Shipment.status.in_(active_statuses),
            Shipment.is_tracking_stale == False,
            or_(
                Shipment.last_tracking_event_at < stale_cutoff,
                and_(
                    Shipment.last_tracking_event_at.is_(None),
                    Shipment.created_at < stale_cutoff,
                ),
            ),
        )

        if organization_id:
            query = query.where(Shipment.organization_id == organization_id)

        shipments = list((await session.execute(query)).scalars().all())

        stale_flagged = 0
        exceptions_created = 0

        for s in shipments:
            s.is_tracking_stale = True
            stale_flagged += 1

            # Log audit event
            last_seen = s.last_tracking_event_at.strftime('%Y-%m-%d %H:%M UTC') if s.last_tracking_event_at else "creation"
            event = ShipmentEvent(
                organization_id=s.organization_id,
                shipment_id=s.id,
                event_type="TRACKING_STALE_DETECTED",
                description=f"Tracking stale: no telematics or milestone update received since {last_seen} (threshold: {threshold_hours}h)",
                occurred_at=now_utc,
                source="SYSTEM",
                payload={"threshold_hours": threshold_hours, "last_event_at": s.last_tracking_event_at.isoformat() if s.last_tracking_event_at else None},
            )
            session.add(event)

            # Record automatic exception
            try:
                await ExceptionService.create_exception(
                    session=session,
                    organization_id=s.organization_id,
                    user_id=None,
                    data=ExceptionCreateRequest(
                        shipment_id=s.id,
                        exception_type=ExceptionType.TRACKING_STALE,
                        severity=ExceptionSeverity.MEDIUM,
                        priority=ExceptionPriority.HIGH,
                        title=f"Stale Tracking Detected ({s.tracking_number})",
                        description=(
                            f"Shipment {s.tracking_number} has not received telematics or milestone pings "
                            f"for more than {threshold_hours} hours. Active monitoring required."
                        ),
                        context_data={
                            "threshold_hours": threshold_hours,
                            "current_status": s.status.value,
                            "current_milestone": s.current_milestone,
                            "last_location": s.last_known_location,
                        },
                    ),
                )
                exceptions_created += 1
            except Exception as e:
                logger.error(f"Error creating TRACKING_STALE exception for shipment {s.id}: {e}")

            # Broadcast stale alert
            alert_payload = {
                "type": "TRACKING_STALE_ALERT",
                "shipment_id": str(s.id),
                "tracking_number": s.tracking_number,
                "is_tracking_stale": True,
                "threshold_hours": threshold_hours,
                "timestamp": now_utc.isoformat(),
            }
            try:
                await tracking_ws_manager.broadcast_shipment_update(str(s.id), alert_payload)
                await tracking_ws_manager.broadcast_org_update(str(s.organization_id), alert_payload)
            except Exception:
                pass

        await session.commit()

        return TrackingScanResponse(
            scanned_count=len(shipments),
            stale_flagged_count=stale_flagged,
            exceptions_created=exceptions_created,
            simulated_now=now_utc.isoformat(),
        )


# Global singleton service
tracking_service = TrackingService()
