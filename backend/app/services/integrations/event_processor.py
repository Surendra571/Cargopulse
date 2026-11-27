import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ExceptionPriority, ExceptionSeverity, ExceptionType, TrackingEventSource
from app.models.integrations import WebhookEvent
from app.models.shipment import Shipment, ShipmentEvent
from app.schemas.exception import ExceptionCreateRequest
from app.services.exception_service import ExceptionService

logger = logging.getLogger(__name__)


class WebhookEventProcessor:
    """
    Background processor for ingested webhook events, applying normalized business updates idempotently.
    """

    async def recover_hung_webhooks(
        self, session: AsyncSession, timeout_seconds: int = 300
    ) -> int:
        """
        Recovers incoming webhooks stuck in PROCESSING due to worker crash.
        Resets them to RECEIVED so another worker can safely pick them up.
        """
        now = datetime.now(timezone.utc)
        threshold = now - timedelta(seconds=timeout_seconds)

        stmt = (
            select(WebhookEvent)
            .where(
                WebhookEvent.status == "PROCESSING",
                WebhookEvent.last_attempt_at <= threshold,
            )
            .with_for_update(skip_locked=True)
        )
        hung_events = (await session.execute(stmt)).scalars().all()
        recovered_count = 0

        for evt in hung_events:
            logger.warning(f"Recovering hung webhook event {evt.id} from {evt.last_attempt_at}")
            evt.status = "RECEIVED"
            recovered_count += 1

        if recovered_count > 0:
            await session.commit()

        return recovered_count

    async def process_received_webhooks(
        self,
        session: AsyncSession,
        organization_id: Optional[uuid.UUID] = None,
        event_id: Optional[uuid.UUID] = None,
        limit: int = 50,
        worker_id: str = "webhook-worker-1",
        simulate_failure_id: Optional[uuid.UUID] = None,
        simulate_permanent_id: Optional[uuid.UUID] = None,
    ) -> Dict[str, Any]:
        """
        Pulls queued RECEIVED or retryable FAILED webhooks using FOR UPDATE SKIP LOCKED.
        Applies business effects idempotently and transitions state.
        """
        now = datetime.now(timezone.utc)

        # 1. Row-level lock acquisition
        stmt = (
            select(WebhookEvent)
            .where(
                WebhookEvent.is_dead_letter == False,
                or_(
                    WebhookEvent.status == "RECEIVED",
                    (
                        (WebhookEvent.status == "FAILED")
                        & (
                            (WebhookEvent.next_retry_at.is_(None))
                            | (WebhookEvent.next_retry_at <= now)
                        )
                    ),
                ),
            )
        )
        if organization_id:
            stmt = stmt.where(
                or_(
                    WebhookEvent.organization_id == organization_id,
                    WebhookEvent.organization_id.is_(None),
                )
            )
        if event_id:
            stmt = stmt.where(WebhookEvent.id == event_id)

        stmt = stmt.order_by(WebhookEvent.created_at.asc()).with_for_update(skip_locked=True).limit(limit)

        events: List[WebhookEvent] = (await session.execute(stmt)).scalars().all()
        if not events:
            return {"processed": 0, "succeeded": 0, "failed": 0, "dead_letter": 0}

        # 2. Mark as PROCESSING
        for evt in events:
            evt.status = "PROCESSING"
            evt.last_attempt_at = now

        await session.commit()

        succeeded_count = 0
        failed_count = 0
        dlq_count = 0

        # 3. Apply business side effects
        for evt in events:
            try:
                # Simulated test failure hooks
                if simulate_permanent_id and evt.id == simulate_permanent_id:
                    raise ValueError("PERMANENT_ERROR: Unrecoverable payload schema mismatch.")
                if simulate_failure_id and evt.id == simulate_failure_id:
                    raise RuntimeError("RETRYABLE_ERROR: Downstream database lock timeout.")

                norm = evt.normalized_payload or {}
                await self._apply_normalized_business_effects(session, evt, norm)

                # Mark as PROCESSED
                evt.status = "PROCESSED"
                evt.processed_at = datetime.now(timezone.utc)
                evt.error_message = None
                evt.error_type = None
                succeeded_count += 1

            except Exception as e:
                err_msg = str(e)
                logger.warning(f"Error processing webhook event {evt.id}: {err_msg}")
                is_permanent = "PERMANENT_ERROR" in err_msg or "schema mismatch" in err_msg.lower()

                evt.error_message = err_msg
                failed_count += 1

                if is_permanent:
                    evt.status = "FAILED"
                    evt.is_dead_letter = True
                    evt.error_type = "PERMANENT"
                    dlq_count += 1
                    await self._create_webhook_failure_exception(session, evt, err_msg, is_permanent=True)
                else:
                    evt.retry_count += 1
                    evt.error_type = "RETRYABLE"
                    if evt.retry_count >= evt.max_retries:
                        evt.status = "FAILED"
                        evt.is_dead_letter = True
                        dlq_count += 1
                        await self._create_webhook_failure_exception(session, evt, err_msg, is_permanent=False)
                    else:
                        evt.status = "FAILED"
                        backoff = min(3600, 2 ** evt.retry_count)
                        evt.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=backoff)

        await session.commit()
        return {
            "processed": len(events),
            "succeeded": succeeded_count,
            "failed": failed_count,
            "dead_letter": dlq_count,
        }

    async def _apply_normalized_business_effects(
        self, session: AsyncSession, evt: WebhookEvent, norm: Dict[str, Any]
    ) -> None:
        """
        Executes idempotent business mutations (Shipment milestone update, location ping recording).
        """
        shipment_id = norm.get("shipment_id")
        tracking_number = norm.get("tracking_number")
        veh_reg = norm.get("vehicle_registration")

        shipment = None

        if shipment_id:
            try:
                shipment_uuid = uuid.UUID(str(shipment_id))
                stmt = select(Shipment).where(Shipment.id == shipment_uuid)
                shipment = (await session.execute(stmt)).scalars().first()
            except ValueError:
                pass

        if not shipment and tracking_number:
            stmt = select(Shipment).where(Shipment.tracking_number == str(tracking_number))
            shipment = (await session.execute(stmt)).scalars().first()

        if not shipment and veh_reg:
            from app.models.transporter import Vehicle
            veh_stmt = select(Vehicle).where(Vehicle.registration_number == str(veh_reg))
            veh = (await session.execute(veh_stmt)).scalars().first()
            if veh:
                stmt = (
                    select(Shipment)
                    .where(Shipment.assigned_vehicle_id == veh.id)
                    .order_by(Shipment.created_at.desc())
                )
                shipment = (await session.execute(stmt)).scalars().first()

        if not shipment:
            logger.info(
                f"Webhook {evt.id} processed: No active shipment matched tracking/vehicle identifier."
            )
            return

        # 1. Update ETA if present
        eta_str = norm.get("estimated_delivery_at")
        if eta_str:
            try:
                shipment.estimated_delivery_at = datetime.fromisoformat(str(eta_str).replace("Z", "+00:00"))
            except Exception:
                pass

        # 2. Append Tracking Event Idempotently
        event_idempotency_key = f"evt_{evt.id}"
        existing_evt_stmt = select(ShipmentEvent).where(
            ShipmentEvent.idempotency_key == event_idempotency_key
        )
        existing_evt = (await session.execute(existing_evt_stmt)).scalars().first()

        if not existing_evt:
            occurred_at = None
            if norm.get("occurred_at"):
                try:
                    occurred_at = datetime.fromisoformat(str(norm.get("occurred_at")).replace("Z", "+00:00"))
                except Exception:
                    occurred_at = datetime.now(timezone.utc)
            else:
                occurred_at = datetime.now(timezone.utc)

            shipment_event = ShipmentEvent(
                organization_id=shipment.organization_id,
                shipment_id=shipment.id,
                milestone=norm.get("milestone"),
                event_type=norm.get("event_type") or "LOCATION_PING",
                description=norm.get("notes") or f"Webhook event from {evt.provider}",
                occurred_at=occurred_at,
                source=TrackingEventSource.WEBHOOK,
                source_identifier=evt.provider,
                latitude=norm.get("latitude"),
                longitude=norm.get("longitude"),
                location_name=norm.get("location_name"),
                speed_kmh=norm.get("speed_kmh"),
                idempotency_key=event_idempotency_key,
                payload=norm.get("raw_payload") or {},
            )
            session.add(shipment_event)

    async def _create_webhook_failure_exception(
        self, session: AsyncSession, evt: WebhookEvent, error_msg: str, is_permanent: bool
    ) -> None:
        """
        Creates an ExceptionRecord in Exception Management when webhook retries are exhausted or permanent.
        """
        if not evt.organization_id:
            return

        try:
            exc_in = ExceptionCreateRequest(
                exception_type=ExceptionType.WEBHOOK_FAILURE,
                severity=ExceptionSeverity.HIGH if is_permanent else ExceptionSeverity.MEDIUM,
                priority=ExceptionPriority.HIGH,
                title=f"Webhook Processing Failure: {evt.provider}",
                description=(
                    f"Webhook event {evt.id} (provider: {evt.provider}, external ID: {evt.external_event_id}) "
                    f"failed processing. Error: {error_msg}."
                ),
                context_data={
                    "webhook_event_id": str(evt.id),
                    "provider": evt.provider,
                    "external_event_id": evt.external_event_id,
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
            logger.error(f"Failed to create exception for webhook failure: {ex}")


event_processor = WebhookEventProcessor()
