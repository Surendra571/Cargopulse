import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.redis import redis_distributed_lock
from app.models.enums import (
    AssignmentStatus,
    BookingStatus,
    CommitmentStatus,
    ExceptionPriority,
    ExceptionSeverity,
    ExceptionStatus,
    ExceptionType,
    NotificationChannel,
    NotificationStatus,
    RecoveryStatus,
    RecoveryStrategy,
    ShipmentStatus,
)
from app.models.integrations import AuditLog, Notification
from app.models.operations import ExceptionRecord, RecoveryCase
from app.models.shipment import (
    PickupCommitment,
    Shipment,
    ShipmentAssignment,
    ShipmentEvent,
    TransporterBooking,
)
from app.models.transporter import Driver, Transporter, Vehicle
from app.schemas.pickup_monitoring import (
    ArrivalReportRequest,
    CommitmentDriverSummary,
    CommitmentShipmentSummary,
    CommitmentTransporterSummary,
    CommitmentVehicleSummary,
    PickupCommitmentListResponse,
    PickupCommitmentResponse,
    PickupCompleteRequest,
    PickupFailRequest,
    PickupScanResponse,
    PickupStartRequest,
    RecoveryApproveRequest,
    RecoveryCaseDetailResponse,
    RecoveryCaseListResponse,
    RecoveryCaseResponse,
    SimulateScenarioRequest,
    SimulateScenarioResponse,
)
from app.services.matching_service import MatchingService


class PickupMonitoringService:
    @classmethod
    async def generate_recovery_case_number(cls, session: AsyncSession, organization_id: uuid.UUID) -> str:
        year = datetime.now(timezone.utc).year
        count_stmt = select(func.count(RecoveryCase.id))
        current_count = (await session.execute(count_stmt)).scalar() or 0
        return f"RCV-{year}-{current_count + 1:06d}"

    @classmethod
    async def _format_commitment_response(cls, commitment: PickupCommitment) -> PickupCommitmentResponse:
        shipment_summary = None
        if hasattr(commitment, "__dict__") and "shipment" in commitment.__dict__ and commitment.shipment:
            s = commitment.shipment
            shipment_summary = CommitmentShipmentSummary(
                id=str(s.id),
                tracking_number=s.tracking_number,
                status=s.status.value if hasattr(s.status, "value") else str(s.status),
                origin_city=s.origin_city,
                origin_state=s.origin_state,
                destination_city=s.destination_city,
                destination_state=s.destination_state,
                total_weight_kg=float(s.total_weight_kg),
                required_vehicle_type=s.custom_metadata.get("required_vehicle_type", "53' Dry Van") if s.custom_metadata else "53' Dry Van",
                scheduled_pickup_time=s.scheduled_pickup_time,
            )

        transporter_summary = None
        if hasattr(commitment, "__dict__") and "transporter" in commitment.__dict__ and commitment.transporter:
            t = commitment.transporter
            transporter_summary = CommitmentTransporterSummary(
                id=str(t.id),
                name=t.name,
                code=t.code,
                phone=t.phone,
                reliability_score=float(t.reliability_score),
            )

        vehicle_summary = None
        if hasattr(commitment, "__dict__") and "vehicle" in commitment.__dict__ and commitment.vehicle:
            v = commitment.vehicle
            vehicle_summary = CommitmentVehicleSummary(
                id=str(v.id),
                license_plate=v.license_plate,
                vehicle_type=v.vehicle_type,
                capacity_kg=float(v.capacity_kg),
            )

        driver_summary = None
        if hasattr(commitment, "__dict__") and "driver" in commitment.__dict__ and commitment.driver:
            d = commitment.driver
            driver_summary = CommitmentDriverSummary(
                id=str(d.id),
                first_name=d.first_name,
                last_name=d.last_name,
                phone=d.phone,
                license_number=d.license_number,
            )

        deadline = commitment.pickup_deadline or commitment.committed_pickup_slot_end

        return PickupCommitmentResponse(
            id=str(commitment.id),
            organization_id=str(commitment.organization_id),
            shipment_id=str(commitment.shipment_id),
            transporter_id=str(commitment.transporter_id),
            booking_id=str(commitment.booking_id) if commitment.booking_id else None,
            committed_pickup_slot_start=commitment.committed_pickup_slot_start,
            committed_pickup_slot_end=commitment.committed_pickup_slot_end,
            pickup_deadline=deadline,
            expected_arrival=commitment.expected_arrival or commitment.committed_pickup_slot_start,
            status=commitment.status,
            actual_arrival_at=commitment.actual_arrival_at,
            is_breached=commitment.is_breached,
            breach_reason=commitment.breach_reason,
            penalties_incurred=float(commitment.penalties_incurred or 0.0),
            created_at=commitment.created_at,
            updated_at=commitment.updated_at,
            shipment=shipment_summary,
            transporter=transporter_summary,
            vehicle=vehicle_summary,
            driver=driver_summary,
        )

    @classmethod
    async def list_commitments(
        cls,
        session: AsyncSession,
        organization_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
        status_filter: Optional[CommitmentStatus] = None,
        shipment_id: Optional[uuid.UUID] = None,
        transporter_id: Optional[uuid.UUID] = None,
        is_breached: Optional[bool] = None,
    ) -> PickupCommitmentListResponse:
        query = (
            select(PickupCommitment)
            .where(
                PickupCommitment.organization_id == organization_id,
                PickupCommitment.is_deleted == False,
            )
            .options(
                selectinload(PickupCommitment.shipment),
                selectinload(PickupCommitment.transporter),
                selectinload(PickupCommitment.vehicle),
                selectinload(PickupCommitment.driver),
            )
        )

        if status_filter:
            query = query.where(PickupCommitment.status == status_filter)
        if shipment_id:
            query = query.where(PickupCommitment.shipment_id == shipment_id)
        if transporter_id:
            query = query.where(PickupCommitment.transporter_id == transporter_id)
        if is_breached is not None:
            query = query.where(PickupCommitment.is_breached == is_breached)

        count_stmt = select(func.count()).select_from(query.subquery())
        total = (await session.execute(count_stmt)).scalar() or 0

        offset = (page - 1) * page_size
        query = query.order_by(desc(PickupCommitment.created_at)).offset(offset).limit(page_size)
        items = list((await session.execute(query)).scalars().all())

        formatted = [await cls._format_commitment_response(c) for c in items]
        pages = (total + page_size - 1) // page_size if page_size > 0 else 1

        return PickupCommitmentListResponse(
            items=formatted,
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        )

    @classmethod
    async def get_commitment(
        cls,
        session: AsyncSession,
        organization_id: uuid.UUID,
        commitment_id: uuid.UUID,
    ) -> PickupCommitmentResponse:
        stmt = (
            select(PickupCommitment)
            .where(
                PickupCommitment.id == commitment_id,
                PickupCommitment.organization_id == organization_id,
                PickupCommitment.is_deleted == False,
            )
            .options(
                selectinload(PickupCommitment.shipment),
                selectinload(PickupCommitment.transporter),
                selectinload(PickupCommitment.vehicle),
                selectinload(PickupCommitment.driver),
            )
        )
        commitment = (await session.execute(stmt)).scalar_one_or_none()
        if not commitment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pickup commitment not found.",
            )
        return await cls._format_commitment_response(commitment)

    @classmethod
    async def report_arrival(
        cls,
        session: AsyncSession,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        commitment_id: uuid.UUID,
        data: ArrivalReportRequest,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> PickupCommitmentResponse:
        """Driver or telematics reporting arrival at pickup dock."""
        now = data.actual_arrival_at or datetime.now(timezone.utc)

        stmt = (
            select(PickupCommitment)
            .where(
                PickupCommitment.id == commitment_id,
                PickupCommitment.organization_id == organization_id,
                PickupCommitment.is_deleted == False,
            )
            .options(selectinload(PickupCommitment.shipment))
            .with_for_update()
        )
        commitment = (await session.execute(stmt)).scalar_one_or_none()
        if not commitment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pickup commitment not found.",
            )

        commitment.actual_arrival_at = now
        commitment.status = CommitmentStatus.ARRIVED

        meta = dict(commitment.commitment_metadata or {})
        if data.dock_number:
            meta["dock_number"] = data.dock_number
        if data.telematics_latitude is not None and data.telematics_longitude is not None:
            meta["telematics_coords"] = [data.telematics_latitude, data.telematics_longitude]
        commitment.commitment_metadata = meta

        if commitment.shipment:
            commitment.shipment.status = ShipmentStatus.AT_PICKUP
            event = ShipmentEvent(
                organization_id=organization_id,
                shipment_id=commitment.shipment.id,
                event_type="ARRIVAL_REPORTED",
                description=f"Carrier reported vehicle arrival at pickup location. Dock: {data.dock_number or 'Standard'}.",
                occurred_at=now,
                source="DRIVER_APP" if not data.telematics_latitude else "TELEMATICS_GEOFENCE",
                created_by_user_id=user_id,
                payload={
                    "commitment_id": str(commitment.id),
                    "arrival_time": now.isoformat(),
                    "notes": data.notes,
                },
            )
            session.add(event)

        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="REPORT_PICKUP_ARRIVAL",
            entity_name="PickupCommitment",
            entity_id=commitment.id,
            ip_address=ip_address,
            user_agent=user_agent,
            changes={"status": CommitmentStatus.ARRIVED.value, "actual_arrival_at": now.isoformat()},
        )
        session.add(audit)

        await session.commit()
        return await cls.get_commitment(session, organization_id, commitment.id)

    @classmethod
    async def start_pickup(
        cls,
        session: AsyncSession,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        commitment_id: uuid.UUID,
        data: PickupStartRequest,
    ) -> PickupCommitmentResponse:
        """Dock loading started."""
        now = data.started_at or datetime.now(timezone.utc)
        stmt = (
            select(PickupCommitment)
            .where(
                PickupCommitment.id == commitment_id,
                PickupCommitment.organization_id == organization_id,
                PickupCommitment.is_deleted == False,
            )
            .options(selectinload(PickupCommitment.shipment))
            .with_for_update()
        )
        commitment = (await session.execute(stmt)).scalar_one_or_none()
        if not commitment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Commitment not found.")

        commitment.status = CommitmentStatus.STARTED
        if commitment.shipment:
            event = ShipmentEvent(
                organization_id=organization_id,
                shipment_id=commitment.shipment.id,
                event_type="PICKUP_STARTED",
                description=f"Cargo loading initiated at dock bay {data.bay_number or 'Main'}.",
                occurred_at=now,
                source="FACILITY_DISPATCH",
                created_by_user_id=user_id,
                payload={"commitment_id": str(commitment.id), "started_at": now.isoformat()},
            )
            session.add(event)

        await session.commit()
        return await cls.get_commitment(session, organization_id, commitment.id)

    @classmethod
    async def complete_pickup(
        cls,
        session: AsyncSession,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        commitment_id: uuid.UUID,
        data: PickupCompleteRequest,
    ) -> PickupCommitmentResponse:
        """Loading complete and cargo in transit."""
        now = data.completed_at or datetime.now(timezone.utc)
        stmt = (
            select(PickupCommitment)
            .where(
                PickupCommitment.id == commitment_id,
                PickupCommitment.organization_id == organization_id,
                PickupCommitment.is_deleted == False,
            )
            .options(selectinload(PickupCommitment.shipment))
            .with_for_update()
        )
        commitment = (await session.execute(stmt)).scalar_one_or_none()
        if not commitment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Commitment not found.")

        commitment.status = CommitmentStatus.COMPLETED
        if commitment.shipment:
            commitment.shipment.status = ShipmentStatus.IN_TRANSIT
            meta = dict(commitment.shipment.custom_metadata or {})
            if data.bill_of_lading_number:
                meta["bol_number"] = data.bill_of_lading_number
            if data.seal_number:
                meta["seal_number"] = data.seal_number
            commitment.shipment.custom_metadata = meta

            event = ShipmentEvent(
                organization_id=organization_id,
                shipment_id=commitment.shipment.id,
                event_type="PICKUP_COMPLETED",
                description=f"Pickup successfully completed. Vehicle departed towards destination.",
                occurred_at=now,
                source="FACILITY_DISPATCH",
                created_by_user_id=user_id,
                payload={
                    "bol": data.bill_of_lading_number,
                    "seal": data.seal_number,
                    "weight_kg": data.loaded_weight_kg,
                },
            )
            session.add(event)

        await session.commit()
        return await cls.get_commitment(session, organization_id, commitment.id)

    @classmethod
    async def report_pickup_failed(
        cls,
        session: AsyncSession,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        commitment_id: uuid.UUID,
        data: PickupFailRequest,
    ) -> PickupCommitmentResponse:
        """Explicitly flags pickup failure and launches recovery immediately."""
        now = datetime.now(timezone.utc)
        stmt = (
            select(PickupCommitment)
            .where(
                PickupCommitment.id == commitment_id,
                PickupCommitment.organization_id == organization_id,
                PickupCommitment.is_deleted == False,
            )
            .options(
                selectinload(PickupCommitment.shipment),
                selectinload(PickupCommitment.transporter),
                selectinload(PickupCommitment.vehicle),
                selectinload(PickupCommitment.driver),
            )
            .with_for_update()
        )
        commitment = (await session.execute(stmt)).scalar_one_or_none()
        if not commitment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Commitment not found.")

        commitment.status = CommitmentStatus.MISSED
        commitment.is_breached = True
        commitment.breach_reason = data.failure_reason
        if data.penalty_amount:
            commitment.penalties_incurred = Decimal(str(data.penalty_amount))

        # Launch recovery
        await cls._handle_missed_commitment(session, organization_id, commitment, now)
        await session.commit()
        return await cls.get_commitment(session, organization_id, commitment.id)

    @classmethod
    async def monitor_commitments(
        cls,
        session: AsyncSession,
        organization_id: uuid.UUID,
        simulated_now: Optional[datetime] = None,
    ) -> PickupScanResponse:
        """
        Scheduled background monitoring of active pickup commitments.
        Enforces distributed Redis lock to ensure single-worker execution.
        Rules:
        - Send reminder 30 mins before deadline.
        - Mark at risk 10 mins before deadline if arrival not confirmed.
        - Detect missed pickup at deadline and launch recovery.
        """
        now = simulated_now or datetime.now(timezone.utc)

        reminders_sent = 0
        at_risk_flagged = 0
        missed_detected = 0
        exceptions_created = 0
        recovery_opened = 0

        # Acquire distributed lock in Redis
        lock_name = f"pickup_monitor_{organization_id}"
        async with redis_distributed_lock(lock_name, ttl_seconds=15) as acquired:
            if not acquired:
                # Another worker is actively executing this cycle
                return PickupScanResponse(
                    scanned_count=0,
                    reminders_sent=0,
                    at_risk_flagged=0,
                    missed_detected=0,
                    exceptions_created=0,
                    recovery_cases_opened=0,
                    simulated_now=now.isoformat(),
                )

            # Query all commitments in monitorable states
            stmt = (
                select(PickupCommitment)
                .where(
                    PickupCommitment.organization_id == organization_id,
                    PickupCommitment.status.in_([
                        CommitmentStatus.CONFIRMED,
                        CommitmentStatus.REMINDER_SENT,
                        CommitmentStatus.AT_RISK,
                    ]),
                    PickupCommitment.is_deleted == False,
                )
                .options(
                    selectinload(PickupCommitment.shipment),
                    selectinload(PickupCommitment.transporter),
                    selectinload(PickupCommitment.vehicle),
                    selectinload(PickupCommitment.driver),
                )
                .with_for_update()
            )
            commitments = list((await session.execute(stmt)).scalars().all())

            for c in commitments:
                deadline = c.pickup_deadline or c.committed_pickup_slot_end
                if not deadline:
                    continue

                # Ensure deadline is timezone-aware
                if deadline.tzinfo is None:
                    deadline = deadline.replace(tzinfo=timezone.utc)

                time_until_deadline = deadline - now

                # Rule 3: Detect missed pickup at configured deadline
                if now >= deadline and c.actual_arrival_at is None:
                    c.status = CommitmentStatus.MISSED
                    c.is_breached = True
                    c.breach_reason = f"Carrier arrival was not confirmed prior to deadline {deadline.isoformat()}."
                    missed_detected += 1

                    ex, rcv = await cls._handle_missed_commitment(session, organization_id, c, now)
                    if ex:
                        exceptions_created += 1
                    if rcv:
                        recovery_opened += 1

                # Rule 2: Mark at risk 10 minutes before deadline
                elif time_until_deadline <= timedelta(minutes=10) and c.status in [
                    CommitmentStatus.CONFIRMED,
                    CommitmentStatus.REMINDER_SENT,
                ] and c.actual_arrival_at is None:
                    c.status = CommitmentStatus.AT_RISK
                    at_risk_flagged += 1

                    if c.shipment:
                        event = ShipmentEvent(
                            organization_id=organization_id,
                            shipment_id=c.shipment.id,
                            event_type="PICKUP_AT_RISK",
                            description=f"Pickup is at risk! Carrier {c.transporter.name if c.transporter else 'Carrier'} has not reported arrival within 10m of deadline.",
                            occurred_at=now,
                            source="MONITORING_ENGINE",
                            payload={"commitment_id": str(c.id), "deadline": deadline.isoformat()},
                        )
                        session.add(event)

                        notif = Notification(
                            organization_id=organization_id,
                            recipient_user_id=None,
                            channel=NotificationChannel.IN_APP,
                            status=NotificationStatus.QUEUED,
                            destination="DISPATCH_MANAGER",
                            title=f"URGENT: Pickup At Risk ({c.shipment.tracking_number})",
                            body=f"Shipment {c.shipment.tracking_number} pickup is due in <10 minutes with no confirmed dock arrival.",
                            metadata_payload={"type": "PICKUP_AT_RISK", "shipment_id": str(c.shipment.id)},
                        )
                        session.add(notif)

                # Rule 1: Send reminder 30 minutes before pickup deadline
                elif time_until_deadline <= timedelta(minutes=30) and c.status == CommitmentStatus.CONFIRMED and c.actual_arrival_at is None:
                    c.status = CommitmentStatus.REMINDER_SENT
                    reminders_sent += 1

                    if c.shipment:
                        event = ShipmentEvent(
                            organization_id=organization_id,
                            shipment_id=c.shipment.id,
                            event_type="PICKUP_REMINDER_SENT",
                            description=f"30-minute pickup reminder sent to carrier {c.transporter.name if c.transporter else 'Carrier'}.",
                            occurred_at=now,
                            source="MONITORING_ENGINE",
                            payload={"commitment_id": str(c.id), "deadline": deadline.isoformat()},
                        )
                        session.add(event)

                        notif = Notification(
                            organization_id=organization_id,
                            recipient_user_id=None,
                            channel=NotificationChannel.IN_APP,
                            status=NotificationStatus.QUEUED,
                            destination=c.transporter.email or "DISPATCH_DESK" if c.transporter else "DISPATCH_DESK",
                            title=f"Pickup SLA Reminder: {c.shipment.tracking_number}",
                            body=f"Your scheduled pickup window expires in 30 minutes at {deadline.strftime('%H:%M UTC')}. Please ensure equipment arrives on schedule.",
                            metadata_payload={"type": "PICKUP_REMINDER", "shipment_id": str(c.shipment.id)},
                        )
                        session.add(notif)

            if commitments:
                await session.commit()

        return PickupScanResponse(
            scanned_count=len(commitments),
            reminders_sent=reminders_sent,
            at_risk_flagged=at_risk_flagged,
            missed_detected=missed_detected,
            exceptions_created=exceptions_created,
            recovery_cases_opened=recovery_opened,
            simulated_now=now.isoformat(),
        )

    @classmethod
    async def _handle_missed_commitment(
        cls,
        session: AsyncSession,
        organization_id: uuid.UUID,
        commitment: PickupCommitment,
        now: datetime,
    ) -> Tuple[Optional[ExceptionRecord], Optional[RecoveryCase]]:
        """
        Executes atomic failure protocol:
        - Updates shipment status to EXCEPTION
        - Creates ExceptionRecord EXACTLY ONCE (idempotent duplicate prevention)
        - Opens RecoveryCase and queries intelligent matching for replacement alternatives
        - Preserves historical failed assignment
        """
        shipment = commitment.shipment
        if not shipment:
            return None, None

        shipment.status = ShipmentStatus.EXCEPTION
        transporter_name = commitment.transporter.name if commitment.transporter else "Carrier"
        driver_name = f"{commitment.driver.first_name} {commitment.driver.last_name}" if commitment.driver else "Unassigned"
        vehicle_plate = commitment.vehicle.license_plate if commitment.vehicle else "Unassigned"

        # 1. Event: PICKUP_FAILED
        event = ShipmentEvent(
            organization_id=organization_id,
            shipment_id=shipment.id,
            event_type="PICKUP_FAILED",
            description=f"Carrier {transporter_name} failed to arrive by pickup deadline. Dock commitment breached.",
            occurred_at=now,
            source="ACCOUNTABILITY_ENGINE",
            payload={
                "commitment_id": str(commitment.id),
                "transporter_id": str(commitment.transporter_id),
                "vehicle_plate": vehicle_plate,
                "driver_name": driver_name,
                "breach_reason": commitment.breach_reason,
            },
        )
        session.add(event)

        # 2. Check if open exception already exists (Exact-Once guarantee)
        dup_stmt = select(ExceptionRecord).where(
            ExceptionRecord.shipment_id == shipment.id,
            ExceptionRecord.exception_type.in_([ExceptionType.MISSED_PICKUP, ExceptionType.PICKUP_OVERDUE]),
            ExceptionRecord.status.in_([
                ExceptionStatus.OPEN,
                ExceptionStatus.ACKNOWLEDGED,
                ExceptionStatus.INVESTIGATING,
                ExceptionStatus.RECOVERY_IN_PROGRESS,
            ]),
            ExceptionRecord.is_deleted == False,
        )
        existing_exc = (await session.execute(dup_stmt)).scalar_one_or_none()

        exception_record = existing_exc
        if not exception_record:
            exception_record = ExceptionRecord(
                id=uuid.uuid4(),
                organization_id=organization_id,
                shipment_id=shipment.id,
                transporter_id=commitment.transporter_id,
                exception_type=ExceptionType.MISSED_PICKUP,
                severity=ExceptionSeverity.CRITICAL,
                priority="CRITICAL",
                status=ExceptionStatus.RECOVERY_IN_PROGRESS,
                title=f"Missed Pickup: {shipment.tracking_number} ({transporter_name})",
                description=(
                    f"Carrier {transporter_name} failed to arrive for scheduled pickup. "
                    f"Assigned vehicle {vehicle_plate}, driver {driver_name}. Automated recovery engaged."
                ),
                reported_at=now,
                context_data={
                    "commitment_id": str(commitment.id),
                    "booking_id": str(commitment.booking_id) if commitment.booking_id else None,
                    "transporter_name": transporter_name,
                    "vehicle_plate": vehicle_plate,
                    "driver_name": driver_name,
                },
            )
            session.add(exception_record)

        # 3. Create RecoveryCase if not already opened
        case_stmt = select(RecoveryCase).where(
            RecoveryCase.exception_id == exception_record.id,
            RecoveryCase.status.in_([RecoveryStatus.OPEN, RecoveryStatus.PROPOSED, RecoveryStatus.EXECUTING]),
            RecoveryCase.is_deleted == False,
        )
        existing_case = (await session.execute(case_stmt)).scalar_one_or_none()

        recovery_case = existing_case
        if not recovery_case:
            case_number = await cls.generate_recovery_case_number(session, organization_id)

            # Query matching engine for alternatives, excluding the failed carrier
            alternatives_list = []
            try:
                ranked = await MatchingService.rank_transporters(
                    session=session,
                    organization_id=organization_id,
                    shipment_id=shipment.id,
                )
                for item in ranked.recommendations:
                    # Exclude the failed carrier from alternatives
                    if item.transporter_id != str(commitment.transporter_id) and item.is_eligible:
                        alternatives_list.append({
                            "transporter_id": item.transporter_id,
                            "transporter_name": item.transporter_name,
                            "transporter_code": item.transporter_code,
                            "reliability_score": item.reliability_score,
                            "match_score": item.match_score,
                            "rank": item.rank,
                            "estimated_cost": item.estimated_cost,
                        })
            except Exception:
                alternatives_list = []

            failure_data = {
                "failed_transporter_id": str(commitment.transporter_id),
                "failed_transporter_name": transporter_name,
                "failed_vehicle_plate": vehicle_plate,
                "failed_driver_name": driver_name,
                "failed_commitment_id": str(commitment.id),
                "failure_timestamp": now.isoformat(),
                "breach_reason": commitment.breach_reason,
            }

            recovery_case = RecoveryCase(
                id=uuid.uuid4(),
                organization_id=organization_id,
                exception_id=exception_record.id,
                shipment_id=shipment.id,
                case_number=case_number,
                strategy=RecoveryStrategy.REASSIGN_TRANSPORTER,
                status=RecoveryStatus.OPEN,
                approval_status="PENDING_APPROVAL",
                proposed_solution=f"Reassign shipment to recommended alternative carrier. {len(alternatives_list)} carriers identified.",
                original_transporter_id=commitment.transporter_id,
                original_booking_id=commitment.booking_id,
                ai_generated=True,
                failure_data=failure_data,
                alternatives_data=alternatives_list,
            )
            session.add(recovery_case)

            # Notification to Dispatch Manager
            notif = Notification(
                organization_id=organization_id,
                recipient_user_id=None,
                channel=NotificationChannel.IN_APP,
                status=NotificationStatus.QUEUED,
                destination="OPERATIONS_MANAGER",
                title=f"Recovery Action Required: {case_number}",
                body=f"Missed pickup for {shipment.tracking_number}. Carrier {transporter_name} failed dock SLA. Review alternative carriers and approve reassignment.",
                metadata_payload={
                    "type": "RECOVERY_CASE_OPENED",
                    "recovery_case_id": str(recovery_case.id),
                    "shipment_id": str(shipment.id),
                },
            )
            session.add(notif)

        return exception_record, recovery_case

    @classmethod
    async def approve_recovery_reassignment(
        cls,
        session: AsyncSession,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        recovery_case_id: uuid.UUID,
        data: RecoveryApproveRequest,
    ) -> RecoveryCaseResponse:
        """
        Operations manager approves reassignment to replacement carrier.
        - Preserves historical failed assignment (marked REASSIGNED).
        - Generates new TransporterBooking for replacement carrier.
        - Marks RecoveryCase as COMPLETED.
        - Resolves ExceptionRecord.
        """
        now = datetime.now(timezone.utc)

        stmt = (
            select(RecoveryCase)
            .where(
                RecoveryCase.id == recovery_case_id,
                RecoveryCase.organization_id == organization_id,
                RecoveryCase.is_deleted == False,
            )
            .options(
                selectinload(RecoveryCase.shipment).selectinload(Shipment.assignments),
                selectinload(RecoveryCase.exception_record),
            )
            .with_for_update()
        )
        case = (await session.execute(stmt)).scalar_one_or_none()
        if not case:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recovery case not found.")

        if case.status == RecoveryStatus.COMPLETED:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Recovery case is already completed.")

        shipment = case.shipment
        if not shipment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shipment not found.")

        # Validate replacement carrier
        t_stmt = select(Transporter).where(
            Transporter.id == data.replacement_transporter_id,
            Transporter.organization_id == organization_id,
            Transporter.is_deleted == False,
        )
        repl_carrier = (await session.execute(t_stmt)).scalar_one_or_none()
        if not repl_carrier:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Replacement carrier not found.")

        # 1. Preserve original assignment history
        for a in shipment.assignments:
            if a.status in [AssignmentStatus.ASSIGNED, AssignmentStatus.ACCEPTED] and not a.is_deleted:
                a.status = AssignmentStatus.REASSIGNED
                a.cancelled_reason = f"Reassigned via recovery case {case.case_number} to {repl_carrier.name}"

        # 2. Create replacement booking tender
        ref_year = now.year
        b_count = (await session.execute(select(func.count(TransporterBooking.id)).where(TransporterBooking.organization_id == organization_id))).scalar() or 0
        booking_ref = f"BKG-{ref_year}-{b_count + 1:06d}"

        new_booking = TransporterBooking(
            id=uuid.uuid4(),
            organization_id=organization_id,
            shipment_id=shipment.id,
            transporter_id=repl_carrier.id,
            booking_reference=booking_ref,
            status=BookingStatus.REQUESTED,
            offered_rate=Decimal(str(data.agreed_rate)) if data.agreed_rate is not None else None,
            agreed_rate=Decimal(str(data.agreed_rate)) if data.agreed_rate is not None else None,
            expires_at=now + timedelta(hours=12),
            vehicle_id=data.vehicle_id,
            driver_id=data.driver_id,
            response_notes=f"Expedited replacement tender via recovery {case.case_number}. {data.notes or ''}".strip(),
        )
        session.add(new_booking)

        # 3. Update RecoveryCase record
        case.status = RecoveryStatus.COMPLETED
        case.approval_status = "APPROVED"
        case.replacement_transporter_id = repl_carrier.id
        case.replacement_booking_id = new_booking.id
        case.approved_by_user_id = user_id
        case.approved_at = now
        case.resolved_at = now
        case.resolution_summary = f"Reassigned to {repl_carrier.name} under tender {booking_ref}. Previous assignment archived."

        # 4. Resolve the ExceptionRecord
        if case.exception_record:
            case.exception_record.status = ExceptionStatus.RESOLVED
            case.exception_record.resolved_at = now
            case.exception_record.resolution_notes = f"Resolved via recovery case {case.case_number}. Transporter {repl_carrier.name} tendered."

        # 5. Update shipment state
        shipment.status = ShipmentStatus.PENDING_ACCEPTANCE
        shipment.updated_at = now

        # 6. Event: RECOVERY_APPROVED
        event = ShipmentEvent(
            organization_id=organization_id,
            shipment_id=shipment.id,
            event_type="RECOVERY_APPROVED",
            description=f"Manager approved recovery reassignment to carrier {repl_carrier.name}. Tender {booking_ref} created.",
            occurred_at=now,
            source="OPERATIONS_DESK",
            created_by_user_id=user_id,
            payload={
                "recovery_case_id": str(case.id),
                "case_number": case.case_number,
                "replacement_transporter_id": str(repl_carrier.id),
                "replacement_transporter_name": repl_carrier.name,
                "replacement_booking_ref": booking_ref,
            },
        )
        session.add(event)

        # 7. Audit log
        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="APPROVE_RECOVERY_REASSIGNMENT",
            entity_name="RecoveryCase",
            entity_id=case.id,
            changes={
                "replacement_transporter_id": str(repl_carrier.id),
                "replacement_booking_ref": booking_ref,
                "approval_status": "APPROVED",
                "status": RecoveryStatus.COMPLETED.value,
            },
        )
        session.add(audit)

        res = RecoveryCaseResponse(
            id=str(case.id),
            organization_id=str(case.organization_id),
            exception_id=str(case.exception_id),
            shipment_id=str(case.shipment_id),
            case_number=case.case_number,
            strategy=case.strategy,
            status=case.status,
            approval_status=case.approval_status,
            proposed_solution=case.proposed_solution,
            estimated_cost_impact=float(case.estimated_cost_impact or 0.0),
            original_transporter_id=str(case.original_transporter_id) if case.original_transporter_id else None,
            replacement_transporter_id=str(case.replacement_transporter_id),
            replacement_booking_id=str(case.replacement_booking_id),
            approved_by_user_id=str(case.approved_by_user_id),
            approved_at=case.approved_at,
            resolved_at=case.resolved_at,
            resolution_summary=case.resolution_summary,
            ai_generated=case.ai_generated,
            failure_data=case.failure_data,
            alternatives_data=case.alternatives_data,
            created_at=case.created_at,
            updated_at=case.updated_at,
        )

        await session.commit()
        return res

    @classmethod
    async def list_recovery_cases(
        cls,
        session: AsyncSession,
        organization_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
        status_filter: Optional[RecoveryStatus] = None,
    ) -> RecoveryCaseListResponse:
        query = select(RecoveryCase).where(
            RecoveryCase.organization_id == organization_id,
            RecoveryCase.is_deleted == False,
        )
        if status_filter:
            query = query.where(RecoveryCase.status == status_filter)

        total = (await session.execute(select(func.count()).select_from(query.subquery()))).scalar() or 0
        offset = (page - 1) * page_size
        items = list((await session.execute(query.order_by(desc(RecoveryCase.created_at)).offset(offset).limit(page_size))).scalars().all())

        formatted = [
            RecoveryCaseResponse(
                id=str(c.id),
                organization_id=str(c.organization_id),
                exception_id=str(c.exception_id),
                shipment_id=str(c.shipment_id) if c.shipment_id else None,
                case_number=c.case_number,
                strategy=c.strategy,
                status=c.status,
                approval_status=c.approval_status,
                proposed_solution=c.proposed_solution,
                estimated_cost_impact=float(c.estimated_cost_impact or 0.0),
                original_transporter_id=str(c.original_transporter_id) if c.original_transporter_id else None,
                replacement_transporter_id=str(c.replacement_transporter_id) if c.replacement_transporter_id else None,
                replacement_booking_id=str(c.replacement_booking_id) if c.replacement_booking_id else None,
                approved_by_user_id=str(c.approved_by_user_id) if c.approved_by_user_id else None,
                approved_at=c.approved_at,
                resolved_at=c.resolved_at,
                resolution_summary=c.resolution_summary,
                ai_generated=c.ai_generated,
                failure_data=c.failure_data,
                alternatives_data=c.alternatives_data,
                created_at=c.created_at,
                updated_at=c.updated_at,
            )
            for c in items
        ]
        pages = (total + page_size - 1) // page_size if page_size > 0 else 1
        return RecoveryCaseListResponse(items=formatted, total=total, page=page, page_size=page_size, pages=pages)

    @classmethod
    async def get_recovery_case(
        cls,
        session: AsyncSession,
        organization_id: uuid.UUID,
        case_id: uuid.UUID,
    ) -> RecoveryCaseResponse:
        stmt = select(RecoveryCase).where(
            RecoveryCase.id == case_id,
            RecoveryCase.organization_id == organization_id,
            RecoveryCase.is_deleted == False,
        )
        c = (await session.execute(stmt)).scalar_one_or_none()
        if not c:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recovery case not found.")

        return RecoveryCaseResponse(
            id=str(c.id),
            organization_id=str(c.organization_id),
            exception_id=str(c.exception_id),
            shipment_id=str(c.shipment_id) if c.shipment_id else None,
            case_number=c.case_number,
            strategy=c.strategy,
            status=c.status,
            approval_status=c.approval_status,
            proposed_solution=c.proposed_solution,
            estimated_cost_impact=float(c.estimated_cost_impact or 0.0),
            original_transporter_id=str(c.original_transporter_id) if c.original_transporter_id else None,
            replacement_transporter_id=str(c.replacement_transporter_id) if c.replacement_transporter_id else None,
            replacement_booking_id=str(c.replacement_booking_id) if c.replacement_booking_id else None,
            approved_by_user_id=str(c.approved_by_user_id) if c.approved_by_user_id else None,
            approved_at=c.approved_at,
            resolved_at=c.resolved_at,
            resolution_summary=c.resolution_summary,
            ai_generated=c.ai_generated,
            failure_data=c.failure_data,
            alternatives_data=c.alternatives_data,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )

    @classmethod
    async def run_simulated_scenario(
        cls,
        session: AsyncSession,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        data: SimulateScenarioRequest,
    ) -> SimulateScenarioResponse:
        """
        Reproducible simulated-time scenario:
        1. A shipment is scheduled for 10 AM.
        2. Transporter A accepts.
        3. Transporter A fails to arrive.
        4. CargoPulse detects the failure at 10 AM.
        5. Transporter C is recommended.
        6. Manager approves.
        7. Replacement booking is created.
        """
        # Base 10:00 AM reference time today
        base_today = datetime.now(timezone.utc).replace(hour=10, minute=0, second=0, microsecond=0)
        pickup_deadline = base_today + timedelta(hours=data.scheduled_hour_offset)

        # 1. Fetch Transporters A and C
        t_stmt = select(Transporter).where(
            Transporter.organization_id == organization_id,
            Transporter.is_active == True,
            Transporter.is_deleted == False,
        ).order_by(Transporter.created_at.asc())
        carriers = list((await session.execute(t_stmt)).scalars().all())
        if len(carriers) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least 2 active transporters are required in your organization to run the simulated demo.",
            )

        carrier_a = None
        carrier_c = None
        v_a = None
        d_a = None

        for c in carriers:
            v = (await session.execute(select(Vehicle).where(Vehicle.transporter_id == c.id, Vehicle.is_deleted == False))).scalars().first()
            d = (await session.execute(select(Driver).where(Driver.transporter_id == c.id, Driver.is_deleted == False))).scalars().first()
            if v and not carrier_a:
                carrier_a = c
                v_a = v
                d_a = d
            elif not carrier_c:
                carrier_c = c

        if not carrier_a:
            carrier_a = carriers[0]
            v_a = (await session.execute(select(Vehicle).where(Vehicle.transporter_id == carrier_a.id, Vehicle.is_deleted == False))).scalars().first()
            if not v_a:
                v_a = Vehicle(
                    id=uuid.uuid4(),
                    organization_id=organization_id,
                    transporter_id=carrier_a.id,
                    license_plate=f"SIM-{uuid.uuid4().hex[:6].upper()}",
                    vehicle_type="53' Dry Van",
                    capacity_kg=Decimal("20000.0"),
                )
                session.add(v_a)
                await session.flush()

        if not carrier_c:
            other_carriers = [c for c in carriers if c.id != carrier_a.id]
            carrier_c = other_carriers[0] if other_carriers else carriers[1]

        # Step 1: Create Shipment scheduled for 10:00 AM
        shipment_ref = f"SHP-{datetime.now(timezone.utc).year}-{int(datetime.now(timezone.utc).timestamp()) % 1000000:06d}"
        shipment = Shipment(
            id=uuid.uuid4(),
            organization_id=organization_id,
            tracking_number=shipment_ref,
            status=ShipmentStatus.COMMITTED,
            origin_name="CargoPulse Distribution Hub",
            origin_address="100 Logistics Park",
            origin_city="Chicago",
            origin_state="IL",
            origin_postal_code="60601",
            origin_contact_name="Dock Master",
            origin_contact_phone="+1-312-555-0100",
            destination_name="Acme Fulfillment Center",
            destination_address="500 Warehouse Way",
            destination_city="Indianapolis",
            destination_state="IN",
            destination_postal_code="46201",
            destination_contact_name="Receiving Manager",
            destination_contact_phone="+1-317-555-0199",
            goods_description="High-value electronics components",
            package_count=10,
            total_weight_kg=Decimal("12000.00"),
            total_volume_cbm=Decimal("45.00"),
            scheduled_pickup_time=pickup_deadline,
            expected_delivery_time=pickup_deadline + timedelta(hours=14),
            custom_metadata={"customer_name": data.customer_name, "required_vehicle_type": "53' Dry Van"},
        )
        session.add(shipment)

        # Step 2: Transporter A accepts tender & commits
        bkg_a_ref = f"BKG-SIM-A-{int(datetime.now(timezone.utc).timestamp()) % 10000}"
        booking_a = TransporterBooking(
            id=uuid.uuid4(),
            organization_id=organization_id,
            shipment_id=shipment.id,
            transporter_id=carrier_a.id,
            booking_reference=bkg_a_ref,
            status=BookingStatus.CONFIRMED,
            offered_rate=Decimal("1950.00"),
            agreed_rate=Decimal("1950.00"),
            confirmed_at=pickup_deadline - timedelta(hours=2),
            expires_at=pickup_deadline + timedelta(hours=4),
            vehicle_id=v_a.id if v_a else None,
            driver_id=d_a.id if d_a else None,
        )
        session.add(booking_a)

        # Active initial assignment
        orig_assignment = ShipmentAssignment(
            id=uuid.uuid4(),
            organization_id=organization_id,
            shipment_id=shipment.id,
            vehicle_id=v_a.id if v_a else None,
            driver_id=d_a.id if d_a else None,
            status=AssignmentStatus.ACCEPTED,
            assigned_at=pickup_deadline - timedelta(hours=2),
        )
        session.add(orig_assignment)

        # Initial commitment
        commitment = PickupCommitment(
            id=uuid.uuid4(),
            organization_id=organization_id,
            shipment_id=shipment.id,
            transporter_id=carrier_a.id,
            booking_id=booking_a.id,
            committed_pickup_slot_start=pickup_deadline,
            committed_pickup_slot_end=pickup_deadline,
            pickup_deadline=pickup_deadline,
            expected_arrival=pickup_deadline,
            assigned_vehicle_id=v_a.id if v_a else None,
            assigned_driver_id=d_a.id if d_a else None,
            status=CommitmentStatus.CONFIRMED,
            is_breached=False,
        )
        session.add(commitment)
        await session.flush()

        milestones = []
        milestones.append({
            "stage": "TENDER_CONFIRMED",
            "time": (pickup_deadline - timedelta(hours=2)).strftime("%I:%M %p"),
            "description": f"Transporter A ({carrier_a.name}) accepted booking {bkg_a_ref} for scheduled 10:00 AM pickup.",
        })

        # Step 3: Advance to T-30m (09:30 AM)
        time_t_minus_30 = pickup_deadline - timedelta(minutes=30)
        commitment.status = CommitmentStatus.REMINDER_SENT
        milestones.append({
            "stage": "REMINDER_DISPATCHED",
            "time": time_t_minus_30.strftime("%I:%M %p"),
            "description": f"30-minute automated pickup SLA reminder dispatched to Transporter A.",
        })

        # Step 4: Advance to T-10m (09:50 AM)
        time_t_minus_10 = pickup_deadline - timedelta(minutes=10)
        commitment.status = CommitmentStatus.AT_RISK
        milestones.append({
            "stage": "MARKED_AT_RISK",
            "time": time_t_minus_10.strftime("%I:%M %p"),
            "description": f"No confirmed dock arrival. Pickup marked AT RISK and escalated to dispatch tower.",
        })

        # Step 5: Advance to 10:00 AM (Deadline breached!)
        commitment.status = CommitmentStatus.MISSED
        commitment.is_breached = True
        commitment.breach_reason = f"Transporter A failed to report arrival by 10:00 AM deadline."

        exc, rcv = await cls._handle_missed_commitment(session, organization_id, commitment, pickup_deadline)
        milestones.append({
            "stage": "FAILURE_DETECTED",
            "time": pickup_deadline.strftime("%I:%M %p"),
            "description": f"Missed pickup detected! Critical exception logged and Recovery Case {rcv.case_number} initiated.",
        })

        # Step 6: Transporter C recommended by intelligence engine
        milestones.append({
            "stage": "ALTERNATIVE_RECOMMENDED",
            "time": (pickup_deadline + timedelta(minutes=1)).strftime("%I:%M %p"),
            "description": f"Transporter C ({carrier_c.name}) identified as #1 eligible replacement carrier (Reliability: {carrier_c.reliability_score:.0f}%).",
        })

        # Step 7: Operations Manager Approves Reassignment
        approval_res = await cls.approve_recovery_reassignment(
            session=session,
            organization_id=organization_id,
            user_id=user_id,
            recovery_case_id=rcv.id,
            data=RecoveryApproveRequest(
                replacement_transporter_id=carrier_c.id,
                agreed_rate=1980.00,
                notes="Simulated dispatch approval for replacement carrier C.",
            ),
        )
        milestones.append({
            "stage": "RECOVERY_APPROVED",
            "time": (pickup_deadline + timedelta(minutes=3)).strftime("%I:%M %p"),
            "description": f"Manager approved reassignment to {carrier_c.name}. Replacement tender {approval_res.replacement_booking_id} created.",
        })

        # Reload assignments to verify history preservation
        assign_stmt = select(ShipmentAssignment).where(ShipmentAssignment.shipment_id == shipment.id)
        assignments = list((await session.execute(assign_stmt)).scalars().all())
        history_records = [
            {
                "id": str(a.id),
                "status": a.status.value,
                "cancelled_reason": a.cancelled_reason,
                "assigned_at": a.assigned_at.isoformat(),
            }
            for a in assignments
        ]

        sim_resp = SimulateScenarioResponse(
            scenario_id=str(uuid.uuid4()),
            status="SUCCESS",
            shipment_id=str(shipment.id),
            tracking_number=shipment.tracking_number,
            transporter_a_name=carrier_a.name,
            transporter_c_name=carrier_c.name,
            pickup_deadline=pickup_deadline.strftime("%Y-%m-%d 10:00:00 UTC"),
            milestones=milestones,
            recovery_case_number=rcv.case_number,
            replacement_booking_ref=approval_res.case_number,
            assignment_history=history_records,
        )

        await session.commit()
        return sim_resp
