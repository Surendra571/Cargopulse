import math
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy import and_, cast, Date, desc, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.auth import User
from app.models.enums import BookingStatus, CommitmentStatus, ShipmentStatus
from app.models.integrations import AuditLog
from app.models.shipment import (
    PickupCommitment,
    Shipment,
    ShipmentAssignment,
    ShipmentEvent,
    TransporterBooking,
)
from app.models.transporter import Transporter
from app.schemas.shipment import (
    PaginatedShipmentsResponse,
    ShipmentAuditLogItem,
    ShipmentCancelRequest,
    ShipmentCreateRequest,
    ShipmentDetailResponse,
    ShipmentEventResponse,
    ShipmentExceptionSummary,
    ShipmentListItem,
    ShipmentUpdateRequest,
    TransporterBookingSummary,
)


class ShipmentService:
    @staticmethod
    async def generate_tracking_number(
        session: AsyncSession,
        organization_id: uuid.UUID,
    ) -> str:
        """
        Generates a unique human-readable tracking number format:
        SHP-{YYYY}-{SEQ:06d} (e.g. SHP-2026-000001).
        """
        year = datetime.now(timezone.utc).year
        prefix = f"SHP-{year}-"

        # Find count of existing shipments for this year in the organization
        count_stmt = select(func.count(Shipment.id)).where(
            and_(
                Shipment.organization_id == organization_id,
                Shipment.tracking_number.like(f"{prefix}%"),
            )
        )
        existing_count = (await session.execute(count_stmt)).scalar() or 0
        sequence = existing_count + 1

        # Check for collision and increment if needed
        while True:
            candidate = f"{prefix}{sequence:06d}"
            collision_stmt = select(Shipment.id).where(
                and_(
                    Shipment.organization_id == organization_id,
                    Shipment.tracking_number == candidate,
                )
            )
            exists = (await session.execute(collision_stmt)).scalar_one_or_none()
            if not exists:
                return candidate
            sequence += 1

    @staticmethod
    async def create_shipment(
        session: AsyncSession,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        data: ShipmentCreateRequest,
    ) -> ShipmentDetailResponse:
        """
        Creates a new shipment with all required specifications, generates
        a human-readable reference, writes immutable event & audit logs inside a transaction.
        """
        # Business Rule 1: Validate weight
        if data.total_weight_kg <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Total cargo weight must be strictly greater than 0 kg.",
            )

        # Business Rule 2: Validate deadlines
        if data.expected_delivery_time <= data.scheduled_pickup_time:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Expected delivery date must be strictly after the scheduled pickup deadline.",
            )

        tracking_number = await ShipmentService.generate_tracking_number(session, organization_id)
        shipment_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        # Store custom metadata
        custom_metadata = {
            "customer_name": data.customer_name,
            "customer_reference": data.customer_reference,
            "cargo_category": data.cargo_category,
            "package_unit": data.package_unit,
            "required_vehicle_type": data.required_vehicle_type,
            "priority": data.priority,
            "special_instructions": data.special_instructions,
        }

        shipment = Shipment(
            id=shipment_id,
            organization_id=organization_id,
            tracking_number=tracking_number,
            status=ShipmentStatus.DRAFT,
            origin_name=data.origin_name,
            origin_address=data.origin_address,
            origin_city=data.origin_city,
            origin_state=data.origin_state,
            origin_postal_code=data.origin_postal_code,
            origin_dock_number=data.origin_dock_number,
            origin_contact_name=data.origin_contact_name,
            origin_contact_phone=data.origin_contact_phone,
            destination_name=data.destination_name,
            destination_address=data.destination_address,
            destination_city=data.destination_city,
            destination_state=data.destination_state,
            destination_postal_code=data.destination_postal_code,
            destination_dock_number=data.destination_dock_number,
            destination_contact_name=data.destination_contact_name,
            destination_contact_phone=data.destination_contact_phone,
            scheduled_pickup_time=data.scheduled_pickup_time,
            expected_delivery_time=data.expected_delivery_time,
            total_weight_kg=data.total_weight_kg,
            total_volume_cbm=data.total_volume_cbm,
            package_count=data.package_count,
            goods_description=data.goods_description,
            is_hazardous=data.is_hazardous,
            invoice_number=data.invoice_number,
            invoice_value=data.invoice_value,
            custom_metadata=custom_metadata,
        )
        session.add(shipment)

        # Record Immutable Shipment Event
        creation_event = ShipmentEvent(
            id=uuid.uuid4(),
            organization_id=organization_id,
            shipment_id=shipment_id,
            event_type="SHIPMENT_CREATED",
            description=f"Shipment {tracking_number} created with {data.package_count} {data.package_unit} ({data.total_weight_kg} kg).",
            occurred_at=now,
            location_name=f"{data.origin_city}, {data.origin_state}",
            source="USER",
            created_by_user_id=user_id,
            payload={
                "customer_name": data.customer_name,
                "tracking_number": tracking_number,
                "priority": data.priority,
            },
        )
        session.add(creation_event)

        # Record Audit Log
        audit_log = AuditLog(
            id=uuid.uuid4(),
            organization_id=organization_id,
            user_id=user_id,
            action="CREATE",
            entity_name="Shipment",
            entity_id=shipment_id,
            changes={
                "tracking_number": tracking_number,
                "customer_name": data.customer_name,
                "origin": f"{data.origin_city}, {data.origin_state}",
                "destination": f"{data.destination_city}, {data.destination_state}",
                "total_weight_kg": data.total_weight_kg,
                "status": "DRAFT",
            },
        )
        session.add(audit_log)

        await session.commit()

        # Return full detail
        return await ShipmentService.get_shipment_detail(session, organization_id, shipment_id)

    @staticmethod
    async def list_shipments(
        session: AsyncSession,
        organization_id: uuid.UUID,
        page: int = 1,
        page_size: int = 10,
        search: Optional[str] = None,
        status_filter: Optional[str] = None,
        priority_filter: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> PaginatedShipmentsResponse:
        """
        Lists tenant shipments with full search, filtering, and pagination.
        """
        filters = [
            Shipment.organization_id == organization_id,
            Shipment.is_deleted.is_(False),
        ]

        if status_filter and status_filter.upper() != "ALL":
            filters.append(Shipment.status == status_filter.upper())

        if priority_filter and priority_filter.upper() != "ALL":
            filters.append(
                Shipment.custom_metadata["priority"].astext == priority_filter.upper()
            )

        if start_date:
            filters.append(Shipment.created_at >= start_date)
        if end_date:
            filters.append(Shipment.created_at <= end_date)

        if search and search.strip():
            s = f"%{search.strip()}%"
            filters.append(
                or_(
                    Shipment.tracking_number.ilike(s),
                    Shipment.goods_description.ilike(s),
                    Shipment.origin_city.ilike(s),
                    Shipment.origin_state.ilike(s),
                    Shipment.destination_city.ilike(s),
                    Shipment.destination_state.ilike(s),
                    Shipment.custom_metadata["customer_name"].astext.ilike(s),
                    Shipment.custom_metadata["customer_reference"].astext.ilike(s),
                )
            )

        # Count total
        count_stmt = select(func.count(Shipment.id)).where(and_(*filters))
        total = (await session.execute(count_stmt)).scalar() or 0
        total_pages = math.ceil(total / page_size) if total > 0 else 1

        # Sorting
        order_col = Shipment.created_at
        if sort_by == "scheduled_pickup_time":
            order_col = Shipment.scheduled_pickup_time
        elif sort_by == "expected_delivery_time":
            order_col = Shipment.expected_delivery_time
        elif sort_by == "tracking_number":
            order_col = Shipment.tracking_number

        order_expression = desc(order_col) if sort_order.lower() == "desc" else order_col.asc()

        stmt = (
            select(Shipment)
            .options(
                selectinload(Shipment.bookings).selectinload(TransporterBooking.transporter),
                selectinload(Shipment.exceptions),
            )
            .where(and_(*filters))
            .order_by(order_expression)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        shipments = (await session.execute(stmt)).scalars().all()

        items: List[ShipmentListItem] = []
        for s in shipments:
            meta = s.custom_metadata or {}

            # Assigned transporter
            t_id = None
            t_name = None
            for b in s.bookings:
                if b.status in [BookingStatus.CONFIRMED, BookingStatus.ACCEPTED] and b.transporter:
                    t_id = str(b.transporter_id)
                    t_name = b.transporter.name
                    break
            if not t_name:
                for b in s.bookings:
                    if b.status in [BookingStatus.REQUESTED, BookingStatus.PENDING_ACCEPTANCE] and b.transporter:
                        t_id = str(b.transporter_id)
                        t_name = b.transporter.name
                        break

            open_exc_cnt = sum(
                1 for e in s.exceptions
                if (e.status.value if hasattr(e.status, "value") else str(e.status)) in ["OPEN", "INVESTIGATING", "RECOVERY_IN_PROGRESS"]
            )

            items.append(
                ShipmentListItem(
                    id=str(s.id),
                    organization_id=str(s.organization_id),
                    tracking_number=s.tracking_number,
                    customer_name=meta.get("customer_name"),
                    customer_reference=meta.get("customer_reference"),
                    status=s.status.value if hasattr(s.status, "value") else str(s.status),
                    priority=meta.get("priority", "STANDARD"),
                    origin_name=s.origin_name,
                    origin_city=s.origin_city,
                    origin_state=s.origin_state,
                    destination_name=s.destination_name,
                    destination_city=s.destination_city,
                    destination_state=s.destination_state,
                    scheduled_pickup_time=s.scheduled_pickup_time,
                    expected_delivery_time=s.expected_delivery_time,
                    actual_pickup_time=s.actual_pickup_time,
                    actual_delivery_time=s.actual_delivery_time,
                    total_weight_kg=float(s.total_weight_kg),
                    package_count=s.package_count,
                    package_unit=meta.get("package_unit", "PALLETS"),
                    required_vehicle_type=meta.get("required_vehicle_type", "53' Dry Van"),
                    cargo_category=meta.get("cargo_category", "GENERAL_FREIGHT"),
                    goods_description=s.goods_description,
                    is_hazardous=s.is_hazardous,
                    assigned_transporter_id=t_id,
                    assigned_transporter_name=t_name,
                    open_exceptions_count=open_exc_cnt,
                    created_at=s.created_at,
                )
            )

        return PaginatedShipmentsResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    @staticmethod
    async def get_shipment_detail(
        session: AsyncSession,
        organization_id: uuid.UUID,
        shipment_id: uuid.UUID,
    ) -> Optional[ShipmentDetailResponse]:
        """
        Fetches full operational and audit detail of a single shipment.
        Strictly enforces tenant isolation (returns None if not owned by org).
        """
        stmt = (
            select(Shipment)
            .options(
                selectinload(Shipment.bookings).selectinload(TransporterBooking.transporter),
                selectinload(Shipment.assignments).selectinload(ShipmentAssignment.vehicle),
                selectinload(Shipment.assignments).selectinload(ShipmentAssignment.driver),
                selectinload(Shipment.events),
                selectinload(Shipment.exceptions),
                selectinload(Shipment.proof_of_delivery),
            )
            .where(
                and_(
                    Shipment.id == shipment_id,
                    Shipment.organization_id == organization_id,
                    Shipment.is_deleted.is_(False),
                )
            )
        )
        shipment = (await session.execute(stmt)).scalar_one_or_none()
        if not shipment:
            return None

        meta = shipment.custom_metadata or {}

        # Assigned transporter
        t_id = None
        t_name = None
        for b in shipment.bookings:
            if b.status in [BookingStatus.CONFIRMED, BookingStatus.ACCEPTED] and b.transporter:
                t_id = str(b.transporter_id)
                t_name = b.transporter.name
                break
        if not t_name:
            for b in shipment.bookings:
                if b.status in [BookingStatus.REQUESTED, BookingStatus.PENDING_ACCEPTANCE] and b.transporter:
                    t_id = str(b.transporter_id)
                    t_name = b.transporter.name
                    break

        # Driver / Vehicle
        driver_name = None
        vehicle_plate = None
        for a in shipment.assignments:
            if a.driver:
                driver_name = f"{a.driver.first_name} {a.driver.last_name}"
            if a.vehicle:
                vehicle_plate = a.vehicle.license_plate
            break

        # Bookings summary
        booking_items = [
            TransporterBookingSummary(
                id=str(bk.id),
                transporter_id=str(bk.transporter_id),
                transporter_name=bk.transporter.name if bk.transporter else "Carrier",
                transporter_code=bk.transporter.code if bk.transporter else "N/A",
                status=bk.status.value if hasattr(bk.status, "value") else str(bk.status),
                offered_rate=float(bk.offered_rate) if bk.offered_rate else None,
                agreed_rate=float(bk.agreed_rate) if bk.agreed_rate else None,
                expires_at=bk.expires_at,
                created_at=bk.created_at,
            )
            for bk in shipment.bookings
        ]

        # Milestone events
        event_items = [
            ShipmentEventResponse(
                id=str(ev.id),
                event_type=ev.event_type,
                description=ev.description,
                occurred_at=ev.occurred_at,
                location_name=ev.location_name,
                source=ev.source,
                created_by_user_id=str(ev.created_by_user_id) if ev.created_by_user_id else None,
            )
            for ev in sorted(shipment.events, key=lambda x: x.occurred_at)
        ]

        # Exceptions
        exc_items = [
            ShipmentExceptionSummary(
                id=str(ex.id),
                exception_type=ex.exception_type.value if hasattr(ex.exception_type, "value") else str(ex.exception_type),
                severity=ex.severity.value if hasattr(ex.severity, "value") else str(ex.severity),
                status=ex.status.value if hasattr(ex.status, "value") else str(ex.status),
                title=ex.title,
                description=ex.description,
                reported_at=ex.reported_at,
                resolved_at=ex.resolved_at,
                resolution_notes=ex.resolution_notes,
            )
            for ex in shipment.exceptions
        ]

        # Fetch Audit History for this shipment
        audit_stmt = (
            select(AuditLog, User.email)
            .outerjoin(User, AuditLog.user_id == User.id)
            .where(
                and_(
                    AuditLog.organization_id == organization_id,
                    AuditLog.entity_name == "Shipment",
                    AuditLog.entity_id == shipment_id,
                )
            )
            .order_by(desc(AuditLog.created_at))
        )
        audit_rows = (await session.execute(audit_stmt)).all()
        audit_items = [
            ShipmentAuditLogItem(
                id=str(log.id),
                action=log.action,
                performed_at=log.created_at,
                user_email=email,
                old_values=log.changes.get("old") if isinstance(log.changes, dict) else None,
                new_values=log.changes.get("new") if isinstance(log.changes, dict) else log.changes,
            )
            for log, email in audit_rows
        ]

        # Proof of Delivery
        pod_verified = False
        pod_signatory = None
        pod_signed_at = None
        pod_doc_url = None
        if shipment.proof_of_delivery:
            pod = shipment.proof_of_delivery
            pod_verified = pod.verification_status.value == "VERIFIED" if hasattr(pod.verification_status, "value") else pod.verification_status == "VERIFIED"
            pod_signatory = pod.signed_by_name
            pod_signed_at = pod.signed_at
            pod_doc_url = pod.document_url

        return ShipmentDetailResponse(
            id=str(shipment.id),
            organization_id=str(shipment.organization_id),
            tracking_number=shipment.tracking_number,
            customer_name=meta.get("customer_name"),
            customer_reference=meta.get("customer_reference"),
            status=shipment.status.value if hasattr(shipment.status, "value") else str(shipment.status),
            priority=meta.get("priority", "STANDARD"),
            origin_name=shipment.origin_name,
            origin_address=shipment.origin_address,
            origin_city=shipment.origin_city,
            origin_state=shipment.origin_state,
            origin_postal_code=shipment.origin_postal_code,
            origin_dock_number=shipment.origin_dock_number,
            origin_contact_name=shipment.origin_contact_name,
            origin_contact_phone=shipment.origin_contact_phone,
            destination_name=shipment.destination_name,
            destination_address=shipment.destination_address,
            destination_city=shipment.destination_city,
            destination_state=shipment.destination_state,
            destination_postal_code=shipment.destination_postal_code,
            destination_dock_number=shipment.destination_dock_number,
            destination_contact_name=shipment.destination_contact_name,
            destination_contact_phone=shipment.destination_contact_phone,
            goods_description=shipment.goods_description,
            cargo_category=meta.get("cargo_category", "GENERAL_FREIGHT"),
            total_weight_kg=float(shipment.total_weight_kg),
            package_count=shipment.package_count,
            package_unit=meta.get("package_unit", "PALLETS"),
            total_volume_cbm=float(shipment.total_volume_cbm) if shipment.total_volume_cbm else None,
            required_vehicle_type=meta.get("required_vehicle_type", "53' Dry Van"),
            is_hazardous=shipment.is_hazardous,
            special_instructions=meta.get("special_instructions"),
            invoice_number=shipment.invoice_number,
            invoice_value=float(shipment.invoice_value) if shipment.invoice_value else None,
            scheduled_pickup_time=shipment.scheduled_pickup_time,
            actual_pickup_time=shipment.actual_pickup_time,
            expected_delivery_time=shipment.expected_delivery_time,
            actual_delivery_time=shipment.actual_delivery_time,
            assigned_transporter_id=t_id,
            assigned_transporter_name=t_name,
            assigned_driver_name=driver_name,
            assigned_vehicle_plate=vehicle_plate,
            bookings=booking_items,
            events=event_items,
            exceptions=exc_items,
            audit_history=audit_items,
            pod_verified=pod_verified,
            pod_signatory_name=pod_signatory,
            pod_signed_at=pod_signed_at,
            pod_document_url=pod_doc_url,
            created_at=shipment.created_at,
            updated_at=shipment.updated_at,
        )

    @staticmethod
    async def update_shipment(
        session: AsyncSession,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        shipment_id: uuid.UUID,
        data: ShipmentUpdateRequest,
    ) -> ShipmentDetailResponse:
        """
        Updates an eligible shipment and records changes in audit history.
        Enforces strict business rules on post-dispatch modifications and cancelled shipments.
        """
        stmt = select(Shipment).where(
            and_(
                Shipment.id == shipment_id,
                Shipment.organization_id == organization_id,
                Shipment.is_deleted.is_(False),
            )
        )
        shipment = (await session.execute(stmt)).scalar_one_or_none()
        if not shipment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Shipment not found or unauthorized.",
            )

        # Business Rule 1: Cannot update cancelled shipments
        if shipment.status == ShipmentStatus.CANCELLED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot modify a shipment that has been cancelled.",
            )

        # Business Rule 2: Cannot modify routing, cargo specs, or scheduled dates after dispatch
        dispatched_statuses = [
            ShipmentStatus.DISPATCHED,
            ShipmentStatus.AT_PICKUP,
            ShipmentStatus.IN_TRANSIT,
            ShipmentStatus.OUT_FOR_DELIVERY,
            ShipmentStatus.DELIVERED,
        ]
        is_dispatched = shipment.status in dispatched_statuses

        locked_fields = [
            "origin_name", "origin_address", "origin_city", "origin_state", "origin_postal_code",
            "destination_name", "destination_address", "destination_city", "destination_state",
            "destination_postal_code", "total_weight_kg", "package_count", "goods_description",
            "scheduled_pickup_time", "expected_delivery_time", "required_vehicle_type", "cargo_category"
        ]

        if is_dispatched:
            # Check if user attempts to modify any locked field
            update_dict = data.model_dump(exclude_unset=True)
            for f in locked_fields:
                if f in update_dict and update_dict[f] is not None:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Field '{f}' cannot be modified after shipment has been dispatched.",
                    )

        # Business Rule 3: Validate deadlines if updated
        new_pickup = data.scheduled_pickup_time or shipment.scheduled_pickup_time
        new_delivery = data.expected_delivery_time or shipment.expected_delivery_time
        if new_delivery <= new_pickup:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Expected delivery date must be strictly after the scheduled pickup deadline.",
            )

        # Business Rule 4: Validate weight if updated
        if data.total_weight_kg is not None and data.total_weight_kg <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Cargo weight must be strictly greater than 0 kg.",
            )

        old_values = {}
        new_values = {}
        meta = dict(shipment.custom_metadata or {})

        # Direct fields update
        direct_fields = [
            "origin_name", "origin_address", "origin_city", "origin_state", "origin_postal_code",
            "origin_dock_number", "origin_contact_name", "origin_contact_phone",
            "destination_name", "destination_address", "destination_city", "destination_state",
            "destination_postal_code", "destination_dock_number", "destination_contact_name",
            "destination_contact_phone", "goods_description", "total_weight_kg", "package_count",
            "total_volume_cbm", "is_hazardous", "scheduled_pickup_time", "expected_delivery_time",
            "invoice_number", "invoice_value"
        ]

        def _json_safe(val: Any) -> Any:
            if val is None:
                return None
            if isinstance(val, (datetime, uuid.UUID)):
                return str(val)
            if hasattr(val, "__float__"):
                return float(val)
            return val

        update_dict = data.model_dump(exclude_unset=True)
        for field in direct_fields:
            if field in update_dict:
                val = getattr(data, field)
                old_val = getattr(shipment, field)
                if old_val != val:
                    old_values[field] = _json_safe(old_val)
                    new_values[field] = _json_safe(val)
                    setattr(shipment, field, val)

        # Custom metadata fields update
        meta_fields = [
            "customer_name", "customer_reference", "cargo_category", "package_unit",
            "required_vehicle_type", "priority", "special_instructions"
        ]
        for mf in meta_fields:
            if mf in update_dict:
                val = getattr(data, mf)
                old_val = meta.get(mf)
                if old_val != val:
                    old_values[mf] = _json_safe(old_val)
                    new_values[mf] = _json_safe(val)
                    meta[mf] = val

        shipment.custom_metadata = meta

        # Record event & audit log only if changes occurred
        if new_values:
            now = datetime.now(timezone.utc)
            event = ShipmentEvent(
                id=uuid.uuid4(),
                organization_id=organization_id,
                shipment_id=shipment.id,
                event_type="SHIPMENT_UPDATED",
                description=f"Shipment details updated: {', '.join(new_values.keys())}.",
                occurred_at=now,
                location_name=f"{shipment.origin_city}, {shipment.origin_state}",
                source="USER",
                created_by_user_id=user_id,
                payload=new_values,
            )
            session.add(event)

            audit_log = AuditLog(
                id=uuid.uuid4(),
                organization_id=organization_id,
                user_id=user_id,
                action="UPDATE",
                entity_name="Shipment",
                entity_id=shipment.id,
                changes={"old": old_values, "new": new_values},
            )
            session.add(audit_log)

        await session.commit()
        return await ShipmentService.get_shipment_detail(session, organization_id, shipment.id)

    @staticmethod
    async def cancel_shipment(
        session: AsyncSession,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        shipment_id: uuid.UUID,
        data: ShipmentCancelRequest,
    ) -> ShipmentDetailResponse:
        """
        Cancels a shipment, invalidates active transporter tenders/commitments,
        and records the cancellation rationale in immutable events & audit logs.
        """
        stmt = (
            select(Shipment)
            .options(
                selectinload(Shipment.bookings),
                selectinload(Shipment.commitments),
            )
            .where(
                and_(
                    Shipment.id == shipment_id,
                    Shipment.organization_id == organization_id,
                    Shipment.is_deleted.is_(False),
                )
            )
        )
        shipment = (await session.execute(stmt)).scalar_one_or_none()
        if not shipment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Shipment not found or unauthorized.",
            )

        # Business Rule 1: Cannot cancel if already cancelled
        if shipment.status == ShipmentStatus.CANCELLED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Shipment is already cancelled.",
            )

        # Business Rule 2: Cannot cancel if already delivered
        if shipment.status == ShipmentStatus.DELIVERED or shipment.actual_delivery_time is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Delivered shipments cannot be cancelled.",
            )

        old_status = shipment.status.value if hasattr(shipment.status, "value") else str(shipment.status)
        shipment.status = ShipmentStatus.CANCELLED

        # Release active bookings
        for b in shipment.bookings:
            if b.status in [BookingStatus.REQUESTED, BookingStatus.ACCEPTED]:
                b.status = BookingStatus.CANCELLED
                b.response_notes = f"Shipment cancelled by shipper: {data.cancellation_reason}"

        # Release commitments
        for c in shipment.commitments:
            if c.status in [CommitmentStatus.PENDING, CommitmentStatus.CONFIRMED]:
                c.status = CommitmentStatus.CANCELLED
                c.breach_reason = f"Cancelled by shipper: {data.cancellation_reason}"

        # Update metadata
        meta = dict(shipment.custom_metadata or {})
        meta["cancellation_reason"] = data.cancellation_reason
        meta["cancelled_at"] = datetime.now(timezone.utc).isoformat()
        shipment.custom_metadata = meta

        now = datetime.now(timezone.utc)

        # Immutable event
        cancel_event = ShipmentEvent(
            id=uuid.uuid4(),
            organization_id=organization_id,
            shipment_id=shipment.id,
            event_type="SHIPMENT_CANCELLED",
            description=f"Shipment cancelled: {data.cancellation_reason}",
            occurred_at=now,
            location_name=f"{shipment.origin_city}, {shipment.origin_state}",
            source="USER",
            created_by_user_id=user_id,
            payload={"reason": data.cancellation_reason, "previous_status": old_status},
        )
        session.add(cancel_event)

        # Audit log
        audit_log = AuditLog(
            id=uuid.uuid4(),
            organization_id=organization_id,
            user_id=user_id,
            action="CANCEL",
            entity_name="Shipment",
            entity_id=shipment.id,
            changes={
                "old": {"status": old_status},
                "new": {"status": "CANCELLED", "cancellation_reason": data.cancellation_reason},
            },
        )
        session.add(audit_log)

        await session.commit()
        return await ShipmentService.get_shipment_detail(session, organization_id, shipment.id)
