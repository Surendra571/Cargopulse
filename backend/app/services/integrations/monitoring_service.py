import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import OutboxStatus
from app.models.integrations import IntegrationConnection, OutboxEvent, WebhookEvent
from app.schemas.integrations import IntegrationDashboardMetrics


class IntegrationMonitoringService:
    """
    Real-time operational intelligence and reliability metrics for CargoPulse Integrations.
    """

    async def get_dashboard_metrics(
        self, session: AsyncSession, organization_id: uuid.UUID
    ) -> IntegrationDashboardMetrics:
        # 1. Webhook metrics
        wh_base = select(WebhookEvent).where(
            or_(
                WebhookEvent.organization_id == organization_id,
                WebhookEvent.organization_id.is_(None),
            )
        )

        total_wh = await session.scalar(select(func.count()).select_from(wh_base.subquery())) or 0
        success_wh = await session.scalar(
            select(func.count()).select_from(wh_base.where(WebhookEvent.status == "PROCESSED").subquery())
        ) or 0
        failed_wh = await session.scalar(
            select(func.count()).select_from(wh_base.where(WebhookEvent.status == "FAILED").subquery())
        ) or 0
        pending_wh = await session.scalar(
            select(func.count()).select_from(
                wh_base.where(WebhookEvent.status.in_(["RECEIVED", "PROCESSING"])).subquery()
            )
        ) or 0
        retry_wh = await session.scalar(
            select(func.count()).select_from(
                wh_base.where(
                    WebhookEvent.retry_count > 0,
                    WebhookEvent.is_dead_letter == False,
                ).subquery()
            )
        ) or 0
        wh_dlq = await session.scalar(
            select(func.count()).select_from(wh_base.where(WebhookEvent.is_dead_letter == True).subquery())
        ) or 0

        # 2. Outbox metrics
        ob_base = select(OutboxEvent).where(OutboxEvent.organization_id == organization_id)

        total_ob = await session.scalar(select(func.count()).select_from(ob_base.subquery())) or 0
        published_ob = await session.scalar(
            select(func.count()).select_from(ob_base.where(OutboxEvent.status == OutboxStatus.PUBLISHED).subquery())
        ) or 0
        pending_ob = await session.scalar(
            select(func.count()).select_from(
                ob_base.where(OutboxEvent.status.in_([OutboxStatus.PENDING, OutboxStatus.PROCESSING])).subquery()
            )
        ) or 0
        failed_ob = await session.scalar(
            select(func.count()).select_from(ob_base.where(OutboxEvent.status == OutboxStatus.FAILED).subquery())
        ) or 0
        ob_dlq = await session.scalar(
            select(func.count()).select_from(
                ob_base.where(
                    or_(
                        OutboxEvent.is_dead_letter == True,
                        OutboxEvent.status == OutboxStatus.DEAD_LETTER,
                    )
                ).subquery()
            )
        ) or 0

        # 3. Connections metrics
        conn_base = select(IntegrationConnection).where(
            IntegrationConnection.organization_id == organization_id,
            IntegrationConnection.is_deleted == False,
        )
        total_conns = await session.scalar(select(func.count()).select_from(conn_base.subquery())) or 0
        healthy_conns = await session.scalar(
            select(func.count()).select_from(
                conn_base.where(
                    IntegrationConnection.is_active == True,
                    IntegrationConnection.health_status == "HEALTHY",
                ).subquery()
            )
        ) or 0

        # 4. Overall System Health determination
        total_dlq = wh_dlq + ob_dlq
        if total_dlq > 10 or (total_conns > 0 and healthy_conns < total_conns * 0.5):
            system_health = "CRITICAL"
        elif total_dlq > 0 or failed_wh > 0 or failed_ob > 0:
            system_health = "DEGRADED"
        else:
            system_health = "HEALTHY"

        # 5. Recent Errors
        recent_err_stmt = (
            select(WebhookEvent)
            .where(
                or_(
                    WebhookEvent.organization_id == organization_id,
                    WebhookEvent.organization_id.is_(None),
                ),
                WebhookEvent.error_message.isnot(None),
            )
            .order_by(WebhookEvent.created_at.desc())
            .limit(10)
        )
        recent_webhook_errors = (await session.execute(recent_err_stmt)).scalars().all()

        recent_errors: List[Dict[str, Any]] = []
        for err in recent_webhook_errors:
            recent_errors.append({
                "id": str(err.id),
                "type": "INBOUND_WEBHOOK",
                "provider": err.provider,
                "error_message": err.error_message,
                "error_type": err.error_type or "GENERAL",
                "timestamp": (err.last_attempt_at or err.created_at).isoformat(),
                "is_dead_letter": err.is_dead_letter,
                "retry_count": err.retry_count,
            })

        return IntegrationDashboardMetrics(
            total_webhooks=total_wh,
            successful_webhooks=success_wh,
            failed_webhooks=failed_wh,
            pending_webhooks=pending_wh,
            retry_webhooks=retry_wh,
            dlq_count=total_dlq,
            total_outbox=total_ob,
            published_outbox=published_ob,
            pending_outbox=pending_ob,
            failed_outbox=failed_ob,
            system_health=system_health,
            connections_count=total_conns,
            healthy_connections_count=healthy_conns,
            recent_errors=recent_errors,
        )


monitoring_service = IntegrationMonitoringService()
