import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.auth import User
from app.models.enums import OutboxStatus
from app.models.integrations import OutboxEvent, WebhookEvent
from app.schemas.integrations import (
    DLQReplayRequest,
    DLQReplayResponse,
    IntegrationConnectionCreate,
    IntegrationConnectionResponse,
    IntegrationConnectionUpdate,
    IntegrationDashboardMetrics,
    OutboxEventResponse,
    WebhookEventResponse,
    WebhookIngestResponse,
)
from app.services.integrations.dlq_service import dlq_service
from app.services.integrations.event_processor import event_processor
from app.services.integrations.monitoring_service import monitoring_service
from app.services.integrations.outbox_service import outbox_service
from app.services.integrations.registry_service import registry_service
from app.services.integrations.webhook_service import webhook_service

router = APIRouter()


# ============================================================================
# Inbound Webhook Ingestion (External Gateways & ERPs)
# ============================================================================

@router.post(
    "/webhooks/{slug_or_id}",
    response_model=WebhookIngestResponse,
    status_code=status.HTTP_200_OK,
    summary="Ingest external transporter/ERP webhook with cryptographic authentication",
)
async def ingest_webhook_endpoint(
    slug_or_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Public/partner webhook receiver endpoint.
    Verifies source authenticity, timestamp freshness, and signature.
    Deduplicates events and safely persists them into PostgreSQL without blocking the sender.
    """
    payload_bytes = await request.body()
    headers_dict = dict(request.headers)
    client_ip = request.client.host if request.client else None

    return await webhook_service.ingest_webhook(
        session=db,
        identifier=slug_or_id,
        payload_bytes=payload_bytes,
        headers=headers_dict,
        client_ip=client_ip,
    )


# ============================================================================
# Integration Registry Management
# ============================================================================

@router.get("/connections", response_model=List[IntegrationConnectionResponse])
async def list_integration_connections(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Lists registered integrations for the user's organization.
    Never exposes raw secrets; returns masked secret previews.
    """
    return await registry_service.list_connections(db, current_user.organization_id)


@router.post("/connections", response_model=IntegrationConnectionResponse, status_code=status.HTTP_201_CREATED)
async def create_integration_connection(
    req: IntegrationConnectionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Registers a new transporter telematics adapter or customer ERP connection.
    """
    return await registry_service.create_connection(db, current_user.organization_id, req)


@router.get("/connections/{connection_id}", response_model=IntegrationConnectionResponse)
async def get_integration_connection(
    connection_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await registry_service.get_connection(db, current_user.organization_id, connection_id)


@router.patch("/connections/{connection_id}", response_model=IntegrationConnectionResponse)
async def update_integration_connection(
    connection_id: uuid.UUID,
    req: IntegrationConnectionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await registry_service.update_connection(db, current_user.organization_id, connection_id, req)


@router.delete("/connections/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_integration_connection(
    connection_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await registry_service.delete_connection(db, current_user.organization_id, connection_id)
    return None


@router.post("/connections/{connection_id}/regenerate-secret")
async def regenerate_webhook_secret(
    connection_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generates a new signing secret for the integration.
    The secret is returned in plain-text ONLY in this response and must be recorded by the operator.
    """
    return await registry_service.regenerate_webhook_secret(db, current_user.organization_id, connection_id)


# ============================================================================
# Webhook and Outbox Event Feeds
# ============================================================================

@router.get("/webhooks", response_model=List[WebhookEventResponse])
async def list_webhook_events(
    status_filter: Optional[str] = Query(None, alias="status"),
    provider: Optional[str] = Query(None),
    is_dead_letter: Optional[bool] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List inbound webhook events with comprehensive filters for debugging and audit.
    """
    stmt = select(WebhookEvent).where(
        or_(
            WebhookEvent.organization_id == current_user.organization_id,
            WebhookEvent.organization_id.is_(None),
        )
    )
    if status_filter:
        stmt = stmt.where(WebhookEvent.status == status_filter.upper())
    if provider:
        stmt = stmt.where(WebhookEvent.provider == provider.lower())
    if is_dead_letter is not None:
        stmt = stmt.where(WebhookEvent.is_dead_letter == is_dead_letter)

    stmt = stmt.order_by(WebhookEvent.created_at.desc()).limit(limit).offset(offset)
    events = (await db.execute(stmt)).scalars().all()
    return list(events)


@router.get("/outbox", response_model=List[OutboxEventResponse])
async def list_outbox_events(
    status_filter: Optional[str] = Query(None, alias="status"),
    aggregate_type: Optional[str] = Query(None),
    is_dead_letter: Optional[bool] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List transactional outbox events with delivery status and retry attempts.
    """
    stmt = select(OutboxEvent).where(OutboxEvent.organization_id == current_user.organization_id)
    if status_filter:
        stmt = stmt.where(OutboxEvent.status == OutboxStatus(status_filter.upper()))
    if aggregate_type:
        stmt = stmt.where(OutboxEvent.aggregate_type == aggregate_type)
    if is_dead_letter is not None:
        stmt = stmt.where(OutboxEvent.is_dead_letter == is_dead_letter)

    stmt = stmt.order_by(OutboxEvent.created_at.desc()).limit(limit).offset(offset)
    events = (await db.execute(stmt)).scalars().all()
    return list(events)


# ============================================================================
# Monitoring Dashboard & Operational Metrics
# ============================================================================

@router.get("/monitoring/dashboard", response_model=IntegrationDashboardMetrics)
async def get_integration_dashboard_metrics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Aggregates health, throughput, error rates, and DLQ status for the integration tower.
    """
    return await monitoring_service.get_dashboard_metrics(db, current_user.organization_id)


# ============================================================================
# Dead-Letter Queue (DLQ) & Manual Replay
# ============================================================================

@router.get("/dlq")
async def list_dead_letter_queue_events(
    event_source: str = Query("webhook", pattern="^(webhook|outbox)$"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await dlq_service.list_dlq_events(
        session=db,
        organization_id=current_user.organization_id,
        event_source=event_source,
        limit=limit,
        offset=offset,
    )


@router.post("/dlq/{event_source}/{event_id}/replay")
async def replay_dead_letter_event_endpoint(
    event_source: str,
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Replays a dead-lettered event, audits the operator action, and runs immediate re-processing.
    """
    if event_source not in ["webhook", "outbox"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="event_source must be 'webhook' or 'outbox'",
        )

    return await dlq_service.replay_single_event(
        session=db,
        event_id=event_id,
        event_source=event_source,
        user_id=current_user.id,
    )


@router.post("/dlq/replay-batch", response_model=DLQReplayResponse)
async def replay_batch_dlq_events_endpoint(
    req: DLQReplayRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await dlq_service.batch_replay(
        session=db,
        event_ids=req.event_ids,
        event_source=req.event_source,
        user_id=current_user.id,
    )


# ============================================================================
# Worker Execution & Maintenance Sweeps
# ============================================================================

@router.post("/outbox/process")
async def trigger_outbox_publisher_sweep(
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Pulls pending transactional outbox events with row-level locks and delivers them.
    """
    return await outbox_service.publish_pending_events(db, limit=limit, worker_id=f"user-{current_user.id}")


@router.post("/webhooks/process")
async def trigger_webhook_processor_sweep(
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Pulls received webhooks and applies idempotent normalized business mutations.
    """
    return await event_processor.process_received_webhooks(db, limit=limit, worker_id=f"user-{current_user.id}")


@router.post("/recover-hung")
async def trigger_hung_event_recovery(
    timeout_seconds: int = Query(300, ge=30, le=3600),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Recovers crashed worker tasks by resetting hung PROCESSING events back to PENDING/RECEIVED.
    """
    recovered_outbox = await outbox_service.recover_hung_events(db, timeout_seconds=timeout_seconds)
    recovered_webhooks = await event_processor.recover_hung_webhooks(db, timeout_seconds=timeout_seconds)
    return {
        "recovered_outbox_events": recovered_outbox,
        "recovered_webhook_events": recovered_webhooks,
    }
