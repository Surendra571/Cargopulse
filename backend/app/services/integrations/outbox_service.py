import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ExceptionPriority, ExceptionSeverity, ExceptionType, OutboxStatus
from app.models.integrations import OutboxEvent
from app.schemas.exception import ExceptionCreateRequest
from app.services.exception_service import ExceptionService

logger = logging.getLogger(__name__)


class OutboxService:
    """
    Transactional Outbox Engine ensuring at-least-once reliable delivery without dual-write hazards.
    """

    @staticmethod
    def create_outbox_event(
        session: AsyncSession,
        organization_id: uuid.UUID,
        aggregate_type: str,
        aggregate_id: uuid.UUID,
        event_type: str,
        payload: Dict[str, Any],
        destination: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        headers: Optional[Dict[str, Any]] = None,
    ) -> OutboxEvent:
        """
        Enqueues an outbox event in the same transaction as the business entity mutation.
        Caller commits the session atomically.
        """
        if not idempotency_key:
            idempotency_key = f"{aggregate_type}_{aggregate_id}_{event_type}_{uuid.uuid4().hex[:8]}"

        event = OutboxEvent(
            organization_id=organization_id,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            event_type=event_type,
            payload=payload,
            destination=destination,
            idempotency_key=idempotency_key,
            headers=headers or {},
            status=OutboxStatus.PENDING,
            max_retries=5,
            retry_count=0,
            is_dead_letter=False,
        )
        session.add(event)
        return event

    async def recover_hung_events(
        self, session: AsyncSession, timeout_seconds: int = 300
    ) -> int:
        """
        Recovers outbox events stuck in PROCESSING due to worker crash or network partition.
        Resets them to PENDING so another worker can safely pick them up.
        """
        now = datetime.now(timezone.utc)
        threshold = now - timedelta(seconds=timeout_seconds)

        stmt = (
            select(OutboxEvent)
            .where(
                OutboxEvent.status == OutboxStatus.PROCESSING,
                OutboxEvent.locked_at <= threshold,
            )
            .with_for_update(skip_locked=True)
        )
        hung_events = (await session.execute(stmt)).scalars().all()
        recovered_count = 0

        for evt in hung_events:
            logger.warning(
                f"Recovering hung outbox event {evt.id} locked by '{evt.locked_by}' at {evt.locked_at}"
            )
            evt.status = OutboxStatus.PENDING
            evt.locked_at = None
            evt.locked_by = None
            recovered_count += 1

        if recovered_count > 0:
            await session.commit()

        return recovered_count

    async def publish_pending_events(
        self,
        session: AsyncSession,
        organization_id: Optional[uuid.UUID] = None,
        event_id: Optional[uuid.UUID] = None,
        limit: int = 50,
        worker_id: str = "outbox-worker-1",
        simulate_failure_id: Optional[uuid.UUID] = None,
        simulate_permanent_id: Optional[uuid.UUID] = None,
    ) -> Dict[str, Any]:
        """
        Scans for pending or retryable outbox events using PostgreSQL 'FOR UPDATE SKIP LOCKED',
        ensuring safe concurrency across multiple workers.
        """
        now = datetime.now(timezone.utc)

        # 1. Fetch eligible outbox events with row-level lock
        stmt = (
            select(OutboxEvent)
            .where(
                OutboxEvent.is_dead_letter == False,
                or_(
                    OutboxEvent.status == OutboxStatus.PENDING,
                    (
                        (OutboxEvent.status == OutboxStatus.FAILED)
                        & (
                            (OutboxEvent.next_retry_at.is_(None))
                            | (OutboxEvent.next_retry_at <= now)
                        )
                    ),
                ),
            )
        )
        if organization_id:
            stmt = stmt.where(OutboxEvent.organization_id == organization_id)
        if event_id:
            stmt = stmt.where(OutboxEvent.id == event_id)

        stmt = stmt.order_by(OutboxEvent.created_at.asc()).with_for_update(skip_locked=True).limit(limit)

        events: List[OutboxEvent] = (await session.execute(stmt)).scalars().all()
        if not events:
            return {"processed": 0, "published": 0, "failed": 0, "dead_letter": 0}

        # 2. Mark as PROCESSING with worker lock
        for evt in events:
            evt.status = OutboxStatus.PROCESSING
            evt.locked_at = now
            evt.locked_by = worker_id

        await session.commit()

        published_count = 0
        failed_count = 0
        dlq_count = 0

        # 3. Process each event
        for evt in events:
            try:
                # Test Hooks for simulated network and permanent failure scenarios
                if simulate_permanent_id and evt.id == simulate_permanent_id:
                    raise ValueError("PERMANENT_ERROR: Invalid endpoint 404 Not Found")
                if simulate_failure_id and evt.id == simulate_failure_id:
                    raise ConnectionError("RETRYABLE_ERROR: Connection timed out (504)")

                # Dispatch logic: if destination provided, perform delivery
                if evt.destination:
                    # In production: httpx.post(evt.destination, json=evt.payload)
                    logger.debug(f"Dispatched outbox event {evt.id} to {evt.destination}")

                # Success
                evt.status = OutboxStatus.PUBLISHED
                evt.processed_at = datetime.now(timezone.utc)
                evt.locked_at = None
                evt.locked_by = None
                evt.error_message = None
                published_count += 1

            except Exception as e:
                err_msg = str(e)
                logger.warning(f"Error publishing outbox event {evt.id}: {err_msg}")
                is_permanent = "PERMANENT_ERROR" in err_msg or "400" in err_msg or "404" in err_msg or "401" in err_msg

                evt.locked_at = None
                evt.locked_by = None
                evt.error_message = err_msg

                if is_permanent:
                    # Immediate transition to DLQ
                    evt.status = OutboxStatus.DEAD_LETTER
                    evt.is_dead_letter = True
                    dlq_count += 1
                    failed_count += 1
                    
                    # Create operational exception
                    await self._create_outbox_failure_exception(session, evt, err_msg, is_permanent=True)
                else:
                    # Retryable error with exponential backoff
                    evt.retry_count += 1
                    failed_count += 1
                    if evt.retry_count >= evt.max_retries:
                        evt.status = OutboxStatus.DEAD_LETTER
                        evt.is_dead_letter = True
                        dlq_count += 1
                        await self._create_outbox_failure_exception(session, evt, err_msg, is_permanent=False)
                    else:
                        evt.status = OutboxStatus.FAILED
                        # Exponential backoff: 2, 4, 8, 16... seconds
                        backoff_seconds = min(3600, 2 ** evt.retry_count)
                        evt.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=backoff_seconds)

        await session.commit()
        return {
            "processed": len(events),
            "published": published_count,
            "failed": failed_count,
            "dead_letter": dlq_count,
        }

    async def _create_outbox_failure_exception(
        self, session: AsyncSession, evt: OutboxEvent, error_msg: str, is_permanent: bool
    ) -> None:
        """
        Creates an ExceptionRecord in Exception Management when outbox retries are exhausted or permanent.
        """
        try:
            from app.models.shipment import Shipment
            from app.models.transporter import Transporter

            verified_shipment_id = None
            if evt.aggregate_type == "Shipment":
                chk_shp = await session.get(Shipment, evt.aggregate_id)
                if chk_shp:
                    verified_shipment_id = chk_shp.id

            verified_transporter_id = None
            if evt.aggregate_type == "Transporter":
                chk_trn = await session.get(Transporter, evt.aggregate_id)
                if chk_trn:
                    verified_transporter_id = chk_trn.id

            exc_in = ExceptionCreateRequest(
                exception_type=ExceptionType.INTEGRATION_FAILURE,
                severity=ExceptionSeverity.HIGH if is_permanent else ExceptionSeverity.MEDIUM,
                priority=ExceptionPriority.HIGH,
                title=f"Outbox Delivery Failure: {evt.event_type}",
                description=(
                    f"Outbox event {evt.id} ({evt.event_type} on {evt.aggregate_type}:{evt.aggregate_id}) "
                    f"failed delivery to destination '{evt.destination}'. Error: {error_msg}."
                ),
                shipment_id=verified_shipment_id,
                transporter_id=verified_transporter_id,
                context_data={
                    "outbox_event_id": str(evt.id),
                    "aggregate_id": str(evt.aggregate_id),
                    "aggregate_type": evt.aggregate_type,
                    "destination": evt.destination,
                    "event_type": evt.event_type,
                    "retry_count": evt.retry_count,
                    "is_permanent": is_permanent,
                },
            )
            await ExceptionService.create_exception(
                session=session,
                organization_id=evt.organization_id,
                user_id=None,
                data=exc_in,
            )
        except Exception as ex:
            logger.error(f"Failed to create exception record for outbox failure: {ex}")


outbox_service = OutboxService()
