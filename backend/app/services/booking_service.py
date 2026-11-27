import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy import desc, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import AssignmentStatus, BookingStatus, CommitmentStatus, NotificationChannel, NotificationStatus, ShipmentStatus
from app.models.integrations import AuditLog, Notification
from app.models.shipment import PickupCommitment, Shipment, ShipmentAssignment, ShipmentEvent, TransporterBooking
from app.models.transporter import Driver, Transporter, Vehicle
from app.schemas.booking import (
    BookingAcceptRequest,
    BookingAssignResourceRequest,
    BookingCancelRequest,
    BookingCreateRequest,
    BookingDetailResponse,
    BookingDriverSummary,
    BookingListResponse,
    BookingRejectRequest,
    BookingResponse,
    BookingShipmentSummary,
    BookingTransporterSummary,
    BookingVehicleSummary,
)


class BookingService:
    @classmethod
    async def generate_booking_reference(cls, session: AsyncSession, organization_id: uuid.UUID) -> str:
        """Generates sequential, human-readable reference e.g. BKG-2026-000001."""
        year = datetime.now(timezone.utc).year
        count_stmt = (
            select(func.count(TransporterBooking.id))
            .where(
                TransporterBooking.organization_id == organization_id,
                func.extract("year", TransporterBooking.created_at) == year,
            )
        )
        current_count = (await session.execute(count_stmt)).scalar() or 0
        return f"BKG-{year}-{current_count + 1:06d}"

    @classmethod
    async def _format_booking_response(
        cls, session: AsyncSession, booking: TransporterBooking
    ) -> BookingResponse:
        now = datetime.now(timezone.utc)
        shipment_summary = None
        if booking.shipment:
            s = booking.shipment
            meta = s.custom_metadata or {}
            shipment_summary = BookingShipmentSummary(
                id=str(s.id),
                tracking_number=s.tracking_number,
                status=s.status.value if hasattr(s.status, "value") else str(s.status),
                customer_name=meta.get("customer_name") or s.origin_contact_name,
                origin_name=s.origin_name,
                origin_city=s.origin_city,
                origin_state=s.origin_state,
                destination_name=s.destination_name,
                destination_city=s.destination_city,
                destination_state=s.destination_state,
                total_weight_kg=float(s.total_weight_kg),
                required_vehicle_type=meta.get("required_vehicle_type") or "53' Dry Van",
                scheduled_pickup_time=s.scheduled_pickup_time,
                expected_delivery_time=s.expected_delivery_time,
            )

        transporter_summary = None
        if booking.transporter:
            t = booking.transporter
            compliance = t.compliance_details or {}
            transporter_summary = BookingTransporterSummary(
                id=str(t.id),
                name=t.name,
                code=t.code,
                phone=t.phone,
                email=t.email,
                verification_status=compliance.get("verification_status", "REGISTERED"),
                reliability_score=float(t.reliability_score),
            )

        vehicle_summary = None
        if booking.vehicle:
            v = booking.vehicle
            vehicle_summary = BookingVehicleSummary(
                id=str(v.id),
                license_plate=v.license_plate,
                vehicle_type=v.vehicle_type,
                capacity_kg=float(v.capacity_kg),
                volume_cbm=float(v.volume_cbm) if v.volume_cbm else None,
                is_available=v.is_available,
                insurance_expiry=v.insurance_expiry,
                fitness_expiry=v.fitness_expiry,
            )

        driver_summary = None
        if booking.driver:
            d = booking.driver
            driver_summary = BookingDriverSummary(
                id=str(d.id),
                first_name=d.first_name,
                last_name=d.last_name,
                phone=d.phone,
                license_number=d.license_number,
                license_expiry=d.license_expiry,
                account_status="AVAILABLE" if d.is_available else "UNAVAILABLE",
            )

        assignment_id = None
        if booking.shipment and booking.shipment.assignments:
            for a in booking.shipment.assignments:
                if a.status in [AssignmentStatus.ASSIGNED, AssignmentStatus.ACCEPTED] and not a.is_deleted:
                    assignment_id = str(a.id)
                    break

        if not assignment_id and booking.shipment_id:
            assign_stmt = select(ShipmentAssignment.id).where(
                ShipmentAssignment.shipment_id == booking.shipment_id,
                ShipmentAssignment.status.in_([AssignmentStatus.ASSIGNED, AssignmentStatus.ACCEPTED]),
                ShipmentAssignment.is_deleted == False,
            ).limit(1)
            active_assign = (await session.execute(assign_stmt)).scalar_one_or_none()
            if active_assign:
                assignment_id = str(active_assign)

        is_expired = (
            now > booking.expires_at
            and booking.status in [BookingStatus.REQUESTED, BookingStatus.PENDING_ACCEPTANCE, BookingStatus.DRAFT]
        )

        return BookingResponse(
            id=str(booking.id),
            organization_id=str(booking.organization_id),
            booking_reference=booking.booking_reference or f"BKG-{booking.id.hex[:8].upper()}",
            status=booking.status,
            shipment_id=str(booking.shipment_id),
            transporter_id=str(booking.transporter_id),
            offered_rate=float(booking.offered_rate) if booking.offered_rate is not None else None,
            agreed_rate=float(booking.agreed_rate) if booking.agreed_rate is not None else None,
            expires_at=booking.expires_at,
            response_notes=booking.response_notes,
            rejection_reason=booking.rejection_reason,
            responded_at=booking.responded_at,
            confirmed_at=booking.confirmed_at,
            cancelled_at=booking.cancelled_at,
            created_at=booking.created_at,
            updated_at=booking.updated_at,
            shipment=shipment_summary,
            transporter=transporter_summary,
            vehicle=vehicle_summary,
            driver=driver_summary,
            assignment_id=assignment_id,
            is_expired=is_expired,
        )

    @classmethod
    async def create_booking(
        cls,
        session: AsyncSession,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        data: BookingCreateRequest,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> BookingResponse:
        """
        Step 1 & 2: Dispatch manager initiates tender booking to eligible carrier.
        Creates TransporterBooking, updates Shipment status, creates notification and audit event.
        """
        now = datetime.now(timezone.utc)

        # 1. Fetch & lock Shipment
        shipment_stmt = (
            select(Shipment)
            .where(
                Shipment.id == data.shipment_id,
                Shipment.organization_id == organization_id,
                Shipment.is_deleted == False,
            )
            .with_for_update()
        )
        shipment = (await session.execute(shipment_stmt)).scalar_one_or_none()
        if not shipment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Shipment not found in your organization.",
            )

        if shipment.status not in [ShipmentStatus.DRAFT, ShipmentStatus.PENDING_ACCEPTANCE]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot create booking for shipment in status '{shipment.status.value}'. Must be DRAFT or PENDING_ACCEPTANCE.",
            )

        # 2. Fetch & validate Transporter
        transporter_stmt = (
            select(Transporter)
            .where(
                Transporter.id == data.transporter_id,
                Transporter.organization_id == organization_id,
                Transporter.is_deleted == False,
            )
        )
        transporter = (await session.execute(transporter_stmt)).scalar_one_or_none()
        if not transporter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Selected transporter not found in your organization.",
            )

        compliance = transporter.compliance_details or {}
        verification_status = compliance.get("verification_status", "REGISTERED")
        if verification_status != "VERIFIED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Transporter '{transporter.name}' is {verification_status}. Only VERIFIED transporters can be booked.",
            )

        if not transporter.is_active or compliance.get("account_status", "ACTIVE") == "SUSPENDED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Transporter '{transporter.name}' is suspended or inactive.",
            )

        # 3. Optional Vehicle & Driver verification at booking creation
        vehicle = None
        if data.vehicle_id:
            v_stmt = select(Vehicle).where(
                Vehicle.id == data.vehicle_id,
                Vehicle.transporter_id == transporter.id,
                Vehicle.organization_id == organization_id,
                Vehicle.is_deleted == False,
            )
            vehicle = (await session.execute(v_stmt)).scalar_one_or_none()
            if not vehicle:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Designated vehicle not found or does not belong to selected carrier.",
                )
            if not vehicle.is_available:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Vehicle '{vehicle.license_plate}' is currently marked unavailable.",
                )
            if float(vehicle.capacity_kg) < float(shipment.total_weight_kg):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Vehicle capacity ({vehicle.capacity_kg}kg) is insufficient for cargo ({shipment.total_weight_kg}kg).",
                )
            if vehicle.insurance_expiry and vehicle.insurance_expiry <= now:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Vehicle '{vehicle.license_plate}' insurance certificate has expired.",
                )

        driver = None
        if data.driver_id:
            d_stmt = select(Driver).where(
                Driver.id == data.driver_id,
                Driver.transporter_id == transporter.id,
                Driver.organization_id == organization_id,
                Driver.is_deleted == False,
            )
            driver = (await session.execute(d_stmt)).scalar_one_or_none()
            if not driver:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Designated driver not found or does not belong to selected carrier.",
                )
            if driver.license_expiry and driver.license_expiry <= now:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Driver '{driver.first_name} {driver.last_name}' license has expired.",
                )

        # 4. Generate reference & create Booking
        booking_ref = await cls.generate_booking_reference(session, organization_id)
        expires_at = now + timedelta(hours=data.expires_in_hours)

        booking = TransporterBooking(
            id=uuid.uuid4(),
            organization_id=organization_id,
            shipment_id=shipment.id,
            transporter_id=transporter.id,
            booking_reference=booking_ref,
            status=BookingStatus.REQUESTED,
            offered_rate=Decimal(str(data.offered_rate)) if data.offered_rate is not None else None,
            agreed_rate=Decimal(str(data.agreed_rate)) if data.agreed_rate is not None else None,
            expires_at=expires_at,
            response_notes=data.booking_notes,
            vehicle_id=vehicle.id if vehicle else None,
            driver_id=driver.id if driver else None,
            booking_metadata={
                "created_by_user_id": str(user_id),
                "expires_in_hours": data.expires_in_hours,
                "initial_offered_rate": data.offered_rate,
            },
        )
        session.add(booking)
        await session.flush()

        # 5. Update Shipment
        meta = dict(shipment.custom_metadata or {})
        meta["assigned_transporter_id"] = str(transporter.id)
        meta["assigned_transporter_name"] = transporter.name
        meta["active_booking_id"] = str(booking.id)
        meta["active_booking_reference"] = booking_ref
        shipment.custom_metadata = meta
        shipment.status = ShipmentStatus.PENDING_ACCEPTANCE
        shipment.updated_at = now

        # 6. Immutable Shipment Event
        rate_str = f"${data.offered_rate:.2f}" if data.offered_rate is not None else "Tariff quote"
        event = ShipmentEvent(
            organization_id=organization_id,
            shipment_id=shipment.id,
            event_type="BOOKING_REQUESTED",
            description=f"Tender {booking_ref} created for carrier {transporter.name} ({rate_str}). Expires in {data.expires_in_hours}h.",
            occurred_at=now,
            source="DISPATCH_CONSOLE",
            created_by_user_id=user_id,
            payload={
                "booking_id": str(booking.id),
                "booking_reference": booking_ref,
                "transporter_id": str(transporter.id),
                "transporter_name": transporter.name,
                "offered_rate": data.offered_rate,
                "expires_at": expires_at.isoformat(),
            },
        )
        session.add(event)

        # 7. Step 3: Asynchronous Transporter Notification
        notification = Notification(
            organization_id=organization_id,
            recipient_user_id=None,
            channel=NotificationChannel.IN_APP,
            status=NotificationStatus.QUEUED,
            destination=transporter.email or transporter.phone,
            title=f"New Dispatch Tender: {booking_ref}",
            body=(
                f"You have received a new shipment tender ({shipment.tracking_number}) from "
                f"{shipment.origin_city}, {shipment.origin_state} to {shipment.destination_city}, {shipment.destination_state}. "
                f"Cargo: {shipment.total_weight_kg}kg. Rate: {rate_str}. Please review and respond within {data.expires_in_hours} hours."
            ),
            metadata_payload={
                "type": "BOOKING_REQUEST",
                "booking_id": str(booking.id),
                "booking_reference": booking_ref,
                "shipment_id": str(shipment.id),
                "tracking_number": shipment.tracking_number,
                "transporter_id": str(transporter.id),
            },
        )
        session.add(notification)

        # 8. Audit Log
        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="CREATE_BOOKING",
            entity_name="TransporterBooking",
            entity_id=booking.id,
            ip_address=ip_address,
            user_agent=user_agent,
            changes={
                "booking_reference": booking_ref,
                "shipment_id": str(shipment.id),
                "transporter_id": str(transporter.id),
                "status": BookingStatus.REQUESTED.value,
                "offered_rate": data.offered_rate,
                "expires_at": expires_at.isoformat(),
            },
        )
        session.add(audit)

        await session.commit()

        # Reload relationships
        return await cls.get_booking(session, organization_id, booking.id)

    @classmethod
    async def get_booking(
        cls,
        session: AsyncSession,
        organization_id: uuid.UUID,
        booking_id: uuid.UUID,
    ) -> BookingResponse:
        """Fetches a single booking with relations and expiration check."""
        stmt = (
            select(TransporterBooking)
            .where(
                TransporterBooking.id == booking_id,
                TransporterBooking.organization_id == organization_id,
                TransporterBooking.is_deleted == False,
            )
            .options(
                selectinload(TransporterBooking.shipment).selectinload(Shipment.assignments),
                selectinload(TransporterBooking.transporter),
                selectinload(TransporterBooking.vehicle),
                selectinload(TransporterBooking.driver),
            )
        )
        booking = (await session.execute(stmt)).scalar_one_or_none()
        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found in your organization.",
            )
        return await cls._format_booking_response(session, booking)

    @classmethod
    async def get_booking_detail(
        cls,
        session: AsyncSession,
        organization_id: uuid.UUID,
        booking_id: uuid.UUID,
    ) -> BookingDetailResponse:
        """Fetches full booking detail including shipment milestone events and audit logs."""
        stmt = (
            select(TransporterBooking)
            .where(
                TransporterBooking.id == booking_id,
                TransporterBooking.organization_id == organization_id,
                TransporterBooking.is_deleted == False,
            )
            .options(
                selectinload(TransporterBooking.shipment).selectinload(Shipment.assignments),
                selectinload(TransporterBooking.shipment).selectinload(Shipment.events),
                selectinload(TransporterBooking.transporter),
                selectinload(TransporterBooking.vehicle),
                selectinload(TransporterBooking.driver),
            )
        )
        booking = (await session.execute(stmt)).scalar_one_or_none()
        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found in your organization.",
            )

        base_res = await cls._format_booking_response(session, booking)

        # Events
        events_list = []
        if booking.shipment and booking.shipment.events:
            for ev in sorted(booking.shipment.events, key=lambda x: x.occurred_at):
                events_list.append({
                    "id": str(ev.id),
                    "event_type": ev.event_type,
                    "description": ev.description,
                    "occurred_at": ev.occurred_at.isoformat(),
                    "source": ev.source,
                })

        # Audit logs
        audit_stmt = (
            select(AuditLog)
            .where(
                AuditLog.organization_id == organization_id,
                AuditLog.entity_id == booking.id,
            )
            .order_by(desc(AuditLog.created_at))
        )
        audit_logs = list((await session.execute(audit_stmt)).scalars().all())
        audit_list = [
            {
                "id": str(al.id),
                "action": al.action,
                "performed_at": al.created_at.isoformat(),
                "new_values": al.changes,
            }
            for al in audit_logs
        ]

        return BookingDetailResponse(
            **base_res.model_dump(),
            events=events_list,
            audit_logs=audit_list,
        )

    @classmethod
    async def list_bookings(
        cls,
        session: AsyncSession,
        organization_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
        shipment_id: Optional[uuid.UUID] = None,
        transporter_id: Optional[uuid.UUID] = None,
        status_filter: Optional[BookingStatus] = None,
        search: Optional[str] = None,
    ) -> BookingListResponse:
        """Paginated list of bookings with filtering."""
        query = (
            select(TransporterBooking)
            .where(
                TransporterBooking.organization_id == organization_id,
                TransporterBooking.is_deleted == False,
            )
            .options(
                selectinload(TransporterBooking.shipment).selectinload(Shipment.assignments),
                selectinload(TransporterBooking.transporter),
                selectinload(TransporterBooking.vehicle),
                selectinload(TransporterBooking.driver),
            )
        )

        if shipment_id:
            query = query.where(TransporterBooking.shipment_id == shipment_id)
        if transporter_id:
            query = query.where(TransporterBooking.transporter_id == transporter_id)
        if status_filter:
            query = query.where(TransporterBooking.status == status_filter)

        if search and search.strip():
            term = f"%{search.strip()}%"
            query = query.join(TransporterBooking.transporter).where(
                or_(
                    TransporterBooking.booking_reference.ilike(term),
                    Transporter.name.ilike(term),
                    Transporter.code.ilike(term),
                )
            )

        # Count total
        count_stmt = select(func.count()).select_from(query.subquery())
        total = (await session.execute(count_stmt)).scalar() or 0

        # Paginate
        offset = (page - 1) * page_size
        query = query.order_by(desc(TransporterBooking.created_at)).offset(offset).limit(page_size)
        items = list((await session.execute(query)).scalars().all())

        formatted_items = [await cls._format_booking_response(session, b) for b in items]
        pages = (total + page_size - 1) // page_size if page_size > 0 else 1

        return BookingListResponse(
            items=formatted_items,
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        )

    @classmethod
    async def accept_booking(
        cls,
        session: AsyncSession,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        booking_id: uuid.UUID,
        data: BookingAcceptRequest,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> BookingResponse:
        """
        Step 5 & 8: Transporter reviews and accepts booking request.
        Concurrency protection: with_for_update() on booking and shipment.
        Idempotency: Re-accepting already accepted/confirmed booking returns cleanly without duplicated events.
        Expiration check: If expired, transitions to EXPIRED and rejects.
        If vehicle & driver are provided on accept, validates and immediately confirms dispatch.
        """
        now = datetime.now(timezone.utc)

        # 1. Lock Booking & Shipment
        booking_stmt = (
            select(TransporterBooking)
            .where(
                TransporterBooking.id == booking_id,
                TransporterBooking.organization_id == organization_id,
                TransporterBooking.is_deleted == False,
            )
            .options(
                selectinload(TransporterBooking.shipment).selectinload(Shipment.assignments),
                selectinload(TransporterBooking.transporter),
            )
            .with_for_update()
        )
        booking = (await session.execute(booking_stmt)).scalar_one_or_none()
        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found in your organization.",
            )

        shipment_stmt = (
            select(Shipment)
            .where(
                Shipment.id == booking.shipment_id,
                Shipment.organization_id == organization_id,
                Shipment.is_deleted == False,
            )
            .with_for_update()
        )
        shipment = (await session.execute(shipment_stmt)).scalar_one_or_none()
        if not shipment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Associated shipment not found.",
            )

        # 2. Idempotency Check
        if booking.status in [BookingStatus.ACCEPTED, BookingStatus.CONFIRMED]:
            # Already accepted; return idempotent success
            return await cls.get_booking(session, organization_id, booking.id)

        # 3. Expiration Check
        if now > booking.expires_at or booking.status == BookingStatus.EXPIRED:
            booking.status = BookingStatus.EXPIRED
            shipment.status = ShipmentStatus.DRAFT
            await session.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tender {booking.booking_reference} expired at {booking.expires_at.isoformat()} and can no longer be accepted.",
            )

        # 4. State validation
        if booking.status not in [BookingStatus.REQUESTED, BookingStatus.PENDING_ACCEPTANCE]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot accept booking in status '{booking.status.value}'. Must be REQUESTED or PENDING_ACCEPTANCE.",
            )

        # 5. Check conflicting active assignments
        for a in shipment.assignments:
            if a.status in [AssignmentStatus.ASSIGNED, AssignmentStatus.ACCEPTED] and not a.is_deleted:
                # Check if conflicting assignment is for another vehicle/carrier
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Shipment {shipment.tracking_number} already has an active assignment.",
                )

        # 6. Apply accepted terms
        booking.responded_at = now
        booking.response_notes = data.response_notes or booking.response_notes
        if data.agreed_rate is not None:
            booking.agreed_rate = Decimal(str(data.agreed_rate))
        elif booking.agreed_rate is None and booking.offered_rate is not None:
            booking.agreed_rate = booking.offered_rate

        transporter_name = booking.transporter.name if booking.transporter else "Carrier"

        # 7. Step 6 & 7: Check if vehicle & driver are provided on acceptance
        vehicle_id = data.vehicle_id or booking.vehicle_id
        driver_id = data.driver_id or booking.driver_id

        if vehicle_id and driver_id:
            # Validate vehicle & driver eligibility
            vehicle, driver = await cls._validate_vehicle_and_driver(
                session, organization_id, booking.transporter_id, shipment, vehicle_id, driver_id
            )

            # Step 8 & 9: Confirm Booking & Activate Assignment
            booking.vehicle_id = vehicle.id
            booking.driver_id = driver.id
            booking.status = BookingStatus.CONFIRMED
            booking.confirmed_at = now

            assignment = ShipmentAssignment(
                id=uuid.uuid4(),
                organization_id=organization_id,
                shipment_id=shipment.id,
                vehicle_id=vehicle.id,
                driver_id=driver.id,
                status=AssignmentStatus.ACCEPTED,
                assigned_at=now,
            )
            session.add(assignment)

            # Auto-record pickup commitment
            commitment = PickupCommitment(
                id=uuid.uuid4(),
                organization_id=organization_id,
                shipment_id=shipment.id,
                transporter_id=booking.transporter_id,
                booking_id=booking.id,
                committed_pickup_slot_start=shipment.scheduled_pickup_time,
                committed_pickup_slot_end=shipment.scheduled_pickup_time,
                pickup_deadline=shipment.scheduled_pickup_time,
                expected_arrival=shipment.scheduled_pickup_time,
                assigned_vehicle_id=vehicle.id,
                assigned_driver_id=driver.id,
                status=CommitmentStatus.CONFIRMED,
                is_breached=False,
            )
            session.add(commitment)

            # Update shipment to COMMITTED
            shipment.status = ShipmentStatus.COMMITTED
            meta = dict(shipment.custom_metadata or {})
            meta["assigned_transporter_id"] = str(booking.transporter_id)
            meta["assigned_transporter_name"] = transporter_name
            meta["assigned_vehicle_plate"] = vehicle.license_plate
            meta["assigned_driver_name"] = f"{driver.first_name} {driver.last_name}"
            meta["confirmed_rate"] = float(booking.agreed_rate) if booking.agreed_rate else None
            shipment.custom_metadata = meta
            shipment.updated_at = now

            # Increment transporter performance counter
            if booking.transporter:
                booking.transporter.total_deliveries += 1

            # Shipment Event
            event = ShipmentEvent(
                organization_id=organization_id,
                shipment_id=shipment.id,
                event_type="BOOKING_CONFIRMED",
                description=f"Tender {booking.booking_reference} confirmed with carrier {transporter_name}. Vehicle: {vehicle.license_plate}, Driver: {driver.first_name} {driver.last_name}.",
                occurred_at=now,
                source="CARRIER_DISPATCH",
                created_by_user_id=user_id,
                payload={
                    "booking_id": str(booking.id),
                    "booking_reference": booking.booking_reference,
                    "vehicle_plate": vehicle.license_plate,
                    "driver_name": f"{driver.first_name} {driver.last_name}",
                    "agreed_rate": float(booking.agreed_rate) if booking.agreed_rate else None,
                },
            )
            session.add(event)

            # Step 10: Manufacturer confirmation notification
            notif = Notification(
                organization_id=organization_id,
                recipient_user_id=None,
                channel=NotificationChannel.IN_APP,
                status=NotificationStatus.QUEUED,
                destination="DISPATCH_DESK",
                title=f"Dispatch Confirmed: {shipment.tracking_number}",
                body=(
                    f"Carrier {transporter_name} has accepted and confirmed dispatch for shipment {shipment.tracking_number}. "
                    f"Assigned vehicle: {vehicle.license_plate} ({vehicle.vehicle_type}), driver: {driver.first_name} {driver.last_name} ({driver.phone}). "
                    f"Status updated to COMMITTED."
                ),
                metadata_payload={
                    "type": "BOOKING_CONFIRMED",
                    "booking_id": str(booking.id),
                    "shipment_id": str(shipment.id),
                    "tracking_number": shipment.tracking_number,
                },
            )
            session.add(notif)
        else:
            # Accepted without immediate vehicle/driver designated yet
            booking.status = BookingStatus.ACCEPTED
            shipment.status = ShipmentStatus.PENDING_ACCEPTANCE
            meta = dict(shipment.custom_metadata or {})
            meta["assigned_transporter_id"] = str(booking.transporter_id)
            meta["assigned_transporter_name"] = transporter_name
            meta["agreed_rate"] = float(booking.agreed_rate) if booking.agreed_rate else None
            shipment.custom_metadata = meta
            shipment.updated_at = now

            event = ShipmentEvent(
                organization_id=organization_id,
                shipment_id=shipment.id,
                event_type="BOOKING_ACCEPTED",
                description=f"Carrier {transporter_name} accepted tender {booking.booking_reference}. Awaiting vehicle & driver allocation.",
                occurred_at=now,
                source="CARRIER_PORTAL",
                created_by_user_id=user_id,
                payload={
                    "booking_id": str(booking.id),
                    "booking_reference": booking.booking_reference,
                    "agreed_rate": float(booking.agreed_rate) if booking.agreed_rate else None,
                },
            )
            session.add(event)

            notif = Notification(
                organization_id=organization_id,
                recipient_user_id=None,
                channel=NotificationChannel.IN_APP,
                status=NotificationStatus.QUEUED,
                destination="DISPATCH_DESK",
                title=f"Tender Accepted: {booking.booking_reference}",
                body=f"Carrier {transporter_name} accepted booking tender {booking.booking_reference} for shipment {shipment.tracking_number}.",
                metadata_payload={
                    "type": "BOOKING_ACCEPTED",
                    "booking_id": str(booking.id),
                    "shipment_id": str(shipment.id),
                },
            )
            session.add(notif)

        # Audit Log
        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="ACCEPT_BOOKING",
            entity_name="TransporterBooking",
            entity_id=booking.id,
            ip_address=ip_address,
            user_agent=user_agent,
            changes={
                "status": booking.status.value,
                "agreed_rate": float(booking.agreed_rate) if booking.agreed_rate else None,
                "vehicle_id": str(booking.vehicle_id) if booking.vehicle_id else None,
                "driver_id": str(booking.driver_id) if booking.driver_id else None,
                "responded_at": now.isoformat(),
            },
        )
        session.add(audit)

        await session.commit()
        return await cls.get_booking(session, organization_id, booking.id)

    @classmethod
    async def reject_booking(
        cls,
        session: AsyncSession,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        booking_id: uuid.UUID,
        data: BookingRejectRequest,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> BookingResponse:
        """
        Step 5: Transporter reviews and rejects booking tender.
        Concurrency protection: with_for_update().
        Idempotency: Repeated rejection returns cleanly.
        """
        now = datetime.now(timezone.utc)

        booking_stmt = (
            select(TransporterBooking)
            .where(
                TransporterBooking.id == booking_id,
                TransporterBooking.organization_id == organization_id,
                TransporterBooking.is_deleted == False,
            )
            .options(
                selectinload(TransporterBooking.shipment),
                selectinload(TransporterBooking.transporter),
            )
            .with_for_update()
        )
        booking = (await session.execute(booking_stmt)).scalar_one_or_none()
        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found in your organization.",
            )

        shipment = booking.shipment
        if not shipment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Associated shipment not found.",
            )

        # Idempotency
        if booking.status == BookingStatus.REJECTED:
            return await cls.get_booking(session, organization_id, booking.id)

        if booking.status == BookingStatus.CONFIRMED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot reject an already CONFIRMED booking. Must use cancel workflow.",
            )

        # Transition booking
        booking.status = BookingStatus.REJECTED
        booking.rejection_reason = data.rejection_reason
        booking.response_notes = data.response_notes or booking.response_notes
        booking.responded_at = now

        # Reset shipment to DRAFT so another carrier can be matched/booked
        shipment.status = ShipmentStatus.DRAFT
        meta = dict(shipment.custom_metadata or {})
        meta["assigned_transporter_id"] = None
        meta["assigned_transporter_name"] = None
        meta["active_booking_id"] = None
        shipment.custom_metadata = meta
        shipment.updated_at = now

        transporter_name = booking.transporter.name if booking.transporter else "Carrier"

        # Shipment Event
        event = ShipmentEvent(
            organization_id=organization_id,
            shipment_id=shipment.id,
            event_type="BOOKING_REJECTED",
            description=f"Carrier {transporter_name} rejected tender {booking.booking_reference}. Reason: {data.rejection_reason}",
            occurred_at=now,
            source="CARRIER_PORTAL",
            created_by_user_id=user_id,
            payload={
                "booking_id": str(booking.id),
                "booking_reference": booking.booking_reference,
                "rejection_reason": data.rejection_reason,
            },
        )
        session.add(event)

        # Notification to dispatch desk
        notif = Notification(
            organization_id=organization_id,
            recipient_user_id=None,
            channel=NotificationChannel.IN_APP,
            status=NotificationStatus.QUEUED,
            destination="DISPATCH_DESK",
            title=f"Tender Rejected: {booking.booking_reference}",
            body=f"Carrier {transporter_name} rejected tender for shipment {shipment.tracking_number}. Reason: {data.rejection_reason}. Shipment reset to DRAFT.",
            metadata_payload={
                "type": "BOOKING_REJECTED",
                "booking_id": str(booking.id),
                "shipment_id": str(shipment.id),
            },
        )
        session.add(notif)

        # Audit Log
        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="REJECT_BOOKING",
            entity_name="TransporterBooking",
            entity_id=booking.id,
            ip_address=ip_address,
            user_agent=user_agent,
            changes={
                "status": BookingStatus.REJECTED.value,
                "rejection_reason": data.rejection_reason,
                "responded_at": now.isoformat(),
            },
        )
        session.add(audit)

        await session.commit()
        return await cls.get_booking(session, organization_id, booking.id)

    @classmethod
    async def assign_resources(
        cls,
        session: AsyncSession,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        booking_id: uuid.UUID,
        data: BookingAssignResourceRequest,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> BookingResponse:
        """
        Step 6 & 7: Transporter supplies vehicle and driver info.
        System validates vehicle eligibility, capacity, document expiration, driver license.
        Booking becomes CONFIRMED, ShipmentAssignment becomes active, Shipment status becomes COMMITTED.
        """
        now = datetime.now(timezone.utc)

        booking_stmt = (
            select(TransporterBooking)
            .where(
                TransporterBooking.id == booking_id,
                TransporterBooking.organization_id == organization_id,
                TransporterBooking.is_deleted == False,
            )
            .options(
                selectinload(TransporterBooking.shipment).selectinload(Shipment.assignments),
                selectinload(TransporterBooking.transporter),
            )
            .with_for_update()
        )
        booking = (await session.execute(booking_stmt)).scalar_one_or_none()
        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found in your organization.",
            )

        shipment = booking.shipment
        if not shipment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Associated shipment not found.",
            )

        if booking.status in [BookingStatus.REJECTED, BookingStatus.CANCELLED, BookingStatus.EXPIRED]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot assign resources to booking in status '{booking.status.value}'.",
            )

        # Validate vehicle and driver
        vehicle, driver = await cls._validate_vehicle_and_driver(
            session, organization_id, booking.transporter_id, shipment, data.vehicle_id, data.driver_id
        )

        # Check existing active assignment
        for a in shipment.assignments:
            if a.status in [AssignmentStatus.ASSIGNED, AssignmentStatus.ACCEPTED] and not a.is_deleted:
                # Cancel old assignment if reassigning on same booking
                a.status = AssignmentStatus.REASSIGNED
                a.cancelled_reason = "Replaced with newly designated unit"

        # Create active assignment
        assignment = ShipmentAssignment(
            id=uuid.uuid4(),
            organization_id=organization_id,
            shipment_id=shipment.id,
            vehicle_id=vehicle.id,
            driver_id=driver.id,
            status=AssignmentStatus.ACCEPTED,
            assigned_at=now,
        )
        session.add(assignment)

        # Auto-record pickup commitment
        commitment = PickupCommitment(
            id=uuid.uuid4(),
            organization_id=organization_id,
            shipment_id=shipment.id,
            transporter_id=booking.transporter_id,
            booking_id=booking.id,
            committed_pickup_slot_start=shipment.scheduled_pickup_time,
            committed_pickup_slot_end=shipment.scheduled_pickup_time,
            pickup_deadline=shipment.scheduled_pickup_time,
            expected_arrival=shipment.scheduled_pickup_time,
            assigned_vehicle_id=vehicle.id,
            assigned_driver_id=driver.id,
            status=CommitmentStatus.CONFIRMED,
            is_breached=False,
        )
        session.add(commitment)

        # Update Booking
        booking.vehicle_id = vehicle.id
        booking.driver_id = driver.id
        booking.status = BookingStatus.CONFIRMED
        booking.confirmed_at = now
        if data.notes:
            booking.response_notes = (
                f"{booking.response_notes or ''}\nDispatch note: {data.notes}".strip()
            )

        # Update Shipment
        shipment.status = ShipmentStatus.COMMITTED
        meta = dict(shipment.custom_metadata or {})
        transporter_name = booking.transporter.name if booking.transporter else "Carrier"
        meta["assigned_transporter_id"] = str(booking.transporter_id)
        meta["assigned_transporter_name"] = transporter_name
        meta["assigned_vehicle_plate"] = vehicle.license_plate
        meta["assigned_driver_name"] = f"{driver.first_name} {driver.last_name}"
        shipment.custom_metadata = meta
        shipment.updated_at = now

        # Shipment Event
        event = ShipmentEvent(
            organization_id=organization_id,
            shipment_id=shipment.id,
            event_type="VEHICLE_ASSIGNED",
            description=f"Vehicle {vehicle.license_plate} ({vehicle.vehicle_type}) and driver {driver.first_name} {driver.last_name} assigned by {transporter_name}.",
            occurred_at=now,
            source="CARRIER_DISPATCH",
            created_by_user_id=user_id,
            payload={
                "booking_id": str(booking.id),
                "vehicle_id": str(vehicle.id),
                "license_plate": vehicle.license_plate,
                "driver_id": str(driver.id),
                "driver_name": f"{driver.first_name} {driver.last_name}",
            },
        )
        session.add(event)

        # Notification
        notif = Notification(
            organization_id=organization_id,
            recipient_user_id=None,
            channel=NotificationChannel.IN_APP,
            status=NotificationStatus.QUEUED,
            destination="DISPATCH_DESK",
            title=f"Vehicle & Driver Assigned: {shipment.tracking_number}",
            body=f"Carrier {transporter_name} allocated vehicle {vehicle.license_plate} and driver {driver.first_name} {driver.last_name} to shipment {shipment.tracking_number}.",
            metadata_payload={
                "type": "RESOURCES_ASSIGNED",
                "booking_id": str(booking.id),
                "shipment_id": str(shipment.id),
            },
        )
        session.add(notif)

        # Audit Log
        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="ASSIGN_BOOKING_RESOURCES",
            entity_name="TransporterBooking",
            entity_id=booking.id,
            ip_address=ip_address,
            user_agent=user_agent,
            changes={
                "vehicle_id": str(vehicle.id),
                "vehicle_plate": vehicle.license_plate,
                "driver_id": str(driver.id),
                "driver_name": f"{driver.first_name} {driver.last_name}",
                "status": BookingStatus.CONFIRMED.value,
            },
        )
        session.add(audit)

        await session.commit()
        return await cls.get_booking(session, organization_id, booking.id)

    @classmethod
    async def cancel_booking(
        cls,
        session: AsyncSession,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        booking_id: uuid.UUID,
        data: BookingCancelRequest,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> BookingResponse:
        """Cancels a booking tender and releases the shipment back to eligible matching pool."""
        now = datetime.now(timezone.utc)

        booking_stmt = (
            select(TransporterBooking)
            .where(
                TransporterBooking.id == booking_id,
                TransporterBooking.organization_id == organization_id,
                TransporterBooking.is_deleted == False,
            )
            .options(
                selectinload(TransporterBooking.shipment).selectinload(Shipment.assignments),
                selectinload(TransporterBooking.transporter),
            )
            .with_for_update()
        )
        booking = (await session.execute(booking_stmt)).scalar_one_or_none()
        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found in your organization.",
            )

        shipment = booking.shipment
        if not shipment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Associated shipment not found.",
            )

        if booking.status == BookingStatus.CANCELLED:
            return await cls.get_booking(session, organization_id, booking.id)

        # Cancel assignments
        for a in shipment.assignments:
            if a.status in [AssignmentStatus.ASSIGNED, AssignmentStatus.ACCEPTED] and not a.is_deleted:
                a.status = AssignmentStatus.CANCELLED
                a.cancelled_reason = f"Booking cancelled: {data.cancellation_reason}"

        booking.status = BookingStatus.CANCELLED
        booking.cancelled_at = now
        booking.rejection_reason = f"Cancelled: {data.cancellation_reason}"

        # Reset shipment to DRAFT
        shipment.status = ShipmentStatus.DRAFT
        meta = dict(shipment.custom_metadata or {})
        meta["assigned_transporter_id"] = None
        meta["assigned_transporter_name"] = None
        meta["assigned_vehicle_plate"] = None
        meta["assigned_driver_name"] = None
        meta["active_booking_id"] = None
        shipment.custom_metadata = meta
        shipment.updated_at = now

        transporter_name = booking.transporter.name if booking.transporter else "Carrier"

        event = ShipmentEvent(
            organization_id=organization_id,
            shipment_id=shipment.id,
            event_type="BOOKING_CANCELLED",
            description=f"Tender {booking.booking_reference} cancelled: {data.cancellation_reason}",
            occurred_at=now,
            source="DISPATCH_CONSOLE",
            created_by_user_id=user_id,
            payload={"booking_id": str(booking.id), "reason": data.cancellation_reason},
        )
        session.add(event)

        notif = Notification(
            organization_id=organization_id,
            recipient_user_id=None,
            channel=NotificationChannel.IN_APP,
            status=NotificationStatus.QUEUED,
            destination="DISPATCH_DESK",
            title=f"Booking Cancelled: {booking.booking_reference}",
            body=f"Booking tender {booking.booking_reference} with carrier {transporter_name} has been cancelled.",
            metadata_payload={"type": "BOOKING_CANCELLED", "booking_id": str(booking.id)},
        )
        session.add(notif)

        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="CANCEL_BOOKING",
            entity_name="TransporterBooking",
            entity_id=booking.id,
            ip_address=ip_address,
            user_agent=user_agent,
            changes={
                "status": BookingStatus.CANCELLED.value,
                "cancellation_reason": data.cancellation_reason,
                "cancelled_at": now.isoformat(),
            },
        )
        session.add(audit)

        await session.commit()
        return await cls.get_booking(session, organization_id, booking.id)

    @classmethod
    async def expire_overdue_bookings(
        cls,
        session: AsyncSession,
        organization_id: uuid.UUID,
    ) -> int:
        """
        Scans for and marks overdue bookings as EXPIRED.
        Resets orphaned shipments to DRAFT so they can be re-tendered.
        """
        now = datetime.now(timezone.utc)
        stmt = (
            select(TransporterBooking)
            .where(
                TransporterBooking.organization_id == organization_id,
                TransporterBooking.status.in_([BookingStatus.REQUESTED, BookingStatus.PENDING_ACCEPTANCE]),
                TransporterBooking.expires_at < now,
                TransporterBooking.is_deleted == False,
            )
            .options(selectinload(TransporterBooking.shipment))
            .with_for_update()
        )
        overdue_bookings = list((await session.execute(stmt)).scalars().all())

        count = 0
        for b in overdue_bookings:
            b.status = BookingStatus.EXPIRED
            count += 1
            if b.shipment and b.shipment.status == ShipmentStatus.PENDING_ACCEPTANCE:
                b.shipment.status = ShipmentStatus.DRAFT

            event = ShipmentEvent(
                organization_id=organization_id,
                shipment_id=b.shipment_id,
                event_type="BOOKING_EXPIRED",
                description=f"Booking tender {b.booking_reference} expired automatically after deadline passed.",
                occurred_at=now,
                source="SYSTEM_EXPIRATION_WORKER",
                payload={"booking_id": str(b.id), "expires_at": b.expires_at.isoformat()},
            )
            session.add(event)

        if count > 0:
            await session.commit()
        return count

    @classmethod
    async def _validate_vehicle_and_driver(
        cls,
        session: AsyncSession,
        organization_id: uuid.UUID,
        transporter_id: uuid.UUID,
        shipment: Shipment,
        vehicle_id: uuid.UUID,
        driver_id: uuid.UUID,
    ) -> Tuple[Vehicle, Driver]:
        """Validates that vehicle and driver belong to carrier, are active, not expired, and meet capacity."""
        now = datetime.now(timezone.utc)

        # 1. Vehicle
        v_stmt = select(Vehicle).where(
            Vehicle.id == vehicle_id,
            Vehicle.transporter_id == transporter_id,
            Vehicle.organization_id == organization_id,
            Vehicle.is_deleted == False,
        )
        vehicle = (await session.execute(v_stmt)).scalar_one_or_none()
        if not vehicle:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Designated vehicle not found or does not belong to carrier.",
            )

        if not vehicle.is_available:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Vehicle '{vehicle.license_plate}' is currently unavailable for dispatch.",
            )

        if float(vehicle.capacity_kg) < float(shipment.total_weight_kg):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Vehicle capacity ({vehicle.capacity_kg}kg) is insufficient for cargo ({shipment.total_weight_kg}kg).",
            )

        if vehicle.insurance_expiry and vehicle.insurance_expiry <= now:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Vehicle '{vehicle.license_plate}' insurance certificate expired on {vehicle.insurance_expiry.strftime('%Y-%m-%d')}.",
            )

        if vehicle.fitness_expiry and vehicle.fitness_expiry <= now:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Vehicle '{vehicle.license_plate}' fitness certificate expired on {vehicle.fitness_expiry.strftime('%Y-%m-%d')}.",
            )

        # 2. Driver
        d_stmt = select(Driver).where(
            Driver.id == driver_id,
            Driver.transporter_id == transporter_id,
            Driver.organization_id == organization_id,
            Driver.is_deleted == False,
        )
        driver = (await session.execute(d_stmt)).scalar_one_or_none()
        if not driver:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Designated driver not found or does not belong to carrier.",
            )

        if not driver.is_available:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Driver '{driver.first_name} {driver.last_name}' is currently unavailable for dispatch.",
            )

        if driver.license_expiry and driver.license_expiry <= now:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Driver '{driver.first_name} {driver.last_name}' commercial license expired on {driver.license_expiry.strftime('%Y-%m-%d')}.",
            )

        return vehicle, driver
