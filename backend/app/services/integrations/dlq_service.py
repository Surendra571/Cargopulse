import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import OutboxStatus
from app.models.integrations import AuditLog, OutboxEvent, WebhookEvent
from app.schemas.integrations import DLQReplayResponse
from app.services.integrations.event_processor import event_processor
from app.services.integrations.outbox_service import outbox_service

logger = logging.getLogger(__name__)


class DeadLetterQueueService:
    """
    Management, replay orchestration, and audit trail for Dead-Letter Queue (DLQ) events.
    """

    async def list_dlq_events(
        self,
        session: AsyncSession,
        organization_id: uuid.UUID,
        event_source: str = "webhook",
        limit: int = 50,
        offset: int = 0,
    ) -> List[Any]:
        if event_source.lower() == "outbox":
            stmt = (
                select(OutboxEvent)
                .where(
                    OutboxEvent.organization_id == organization_id,
                    or_(
                        OutboxEvent.is_dead_letter == True,
                        OutboxEvent.status == OutboxStatus.DEAD_LETTER,
                    ),
                )
                .order_by(OutboxEvent.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            return list((await session.execute(stmt)).scalars().all())
        else:
            stmt = (
                select(WebhookEvent)
                .where(
                    or_(
                        WebhookEvent.organization_id == organization_id,
                        WebhookEvent.organization_id.is_(None),
                    ),
                    WebhookEvent.is_dead_letter == True,
                )
                .order_by(WebhookEvent.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            return list((await session.execute(stmt)).scalars().all())

    async def replay_single_event(
        self,
        session: AsyncSession,
        event_id: uuid.UUID,
        event_source: str = "webhook",
        user_id: Optional[uuid.UUID] = None,
    ) -> Dict[str, Any]:
        """
        Replays a dead-letter event, resetting its status to PENDING/RECEIVED,
        recording an audit trail, and immediately triggering execution.
        """
        now = datetime.now(timezone.utc)

        if event_source.lower() == "outbox":
            stmt = select(OutboxEvent).where(OutboxEvent.id == event_id)
            event: Optional[OutboxEvent] = (await session.execute(stmt)).scalar_one_or_none()
            if not event:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Outbox event '{event_id}' not found.",
                )

            # Reset event state
            event.is_dead_letter = False
            event.status = OutboxStatus.PENDING
            event.retry_count = 0
            event.next_retry_at = None
            event.locked_at = None
            event.locked_by = None
            event.replay_count += 1
            event.last_replayed_at = now
            event.last_replayed_by_id = user_id

            # Create immutable AuditLog
            audit = AuditLog(
                organization_id=event.organization_id,
                user_id=user_id,
                action="REPLAY_DLQ_EVENT",
                entity_name="OutboxEvent",
                entity_id=event.id,
                changes={
                    "event_source": "outbox",
                    "previous_error": event.error_message,
                    "replay_count": event.replay_count,
                    "replayed_at": now.isoformat(),
                },
            )
            session.add(audit)
            await session.commit()

            # Trigger immediate delivery
            result = await outbox_service.publish_pending_events(session, event_id=event.id, limit=1)
            return {
                "event_id": str(event.id),
                "event_source": "outbox",
                "status": "REPLAYED",
                "delivery_result": result,
            }

        else:
            stmt = select(WebhookEvent).where(WebhookEvent.id == event_id)
            webhook_evt: Optional[WebhookEvent] = (await session.execute(stmt)).scalar_one_or_none()
            if not webhook_evt:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Webhook event '{event_id}' not found.",
                )

            # Reset webhook state
            webhook_evt.is_dead_letter = False
            webhook_evt.status = "RECEIVED"
            webhook_evt.retry_count = 0
            webhook_evt.next_retry_at = None
            webhook_evt.error_type = None
            webhook_evt.replay_count += 1
            webhook_evt.last_replayed_at = now
            webhook_evt.last_replayed_by_id = user_id

            # Create immutable AuditLog
            if webhook_evt.organization_id:
                audit = AuditLog(
                    organization_id=webhook_evt.organization_id,
                    user_id=user_id,
                    action="REPLAY_DLQ_EVENT",
                    entity_name="WebhookEvent",
                    entity_id=webhook_evt.id,
                    changes={
                        "event_source": "webhook",
                        "previous_error": webhook_evt.error_message,
                        "replay_count": webhook_evt.replay_count,
                        "replayed_at": now.isoformat(),
                    },
                )
                session.add(audit)

            await session.commit()

            # Trigger immediate processing
            result = await event_processor.process_received_webhooks(session, event_id=webhook_evt.id, limit=1)
            return {
                "event_id": str(webhook_evt.id),
                "event_source": "webhook",
                "status": "REPLAYED",
                "processing_result": result,
            }

    async def batch_replay(
        self,
        session: AsyncSession,
        event_ids: List[uuid.UUID],
        event_source: str = "webhook",
        user_id: Optional[uuid.UUID] = None,
    ) -> DLQReplayResponse:
        replayed = []
        failed = []

        for eid in event_ids:
            try:
                res = await self.replay_single_event(
                    session=session,
                    event_id=eid,
                    event_source=event_source,
                    user_id=user_id,
                )
                replayed.append(res)
            except Exception as e:
                failed.append({"event_id": str(eid), "error": str(e)})

        return DLQReplayResponse(
            replayed_count=len(replayed),
            failed_count=len(failed),
            details=replayed + failed,
        )


dlq_service = DeadLetterQueueService()
