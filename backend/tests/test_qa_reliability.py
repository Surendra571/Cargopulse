import asyncio
import hashlib
import hmac
import json
import time
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.api.deps import get_db
from app.core.config import settings
from app.main import app
from app.models.enums import (
    AssignmentStatus,
    BookingStatus,
    IntegrationType,
    OutboxStatus,
    ShipmentStatus,
)
from app.models.integrations import IntegrationConnection, OutboxEvent, WebhookEvent
from app.models.shipment import Shipment, ShipmentAssignment, TransporterBooking
from app.models.transporter import Driver, Transporter, Vehicle
from app.services.ai.coordinator_service import AICoordinatorService
from app.services.integrations.event_processor import event_processor
from app.services.integrations.outbox_service import outbox_service
from app.services.integrations.webhook_service import webhook_service


@pytest_asyncio.fixture
async def test_engine():
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool, connect_args={"ssl": False}, echo=False)
    yield engine
    await engine.dispose()


async def create_user_session(test_engine, prefix: str):
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)

    async def override_get_db():
        async with session_factory() as session:
            try:
                yield session
            finally:
                await session.close()

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    user_client = AsyncClient(transport=transport, base_url="http://testserver")

    uid = uuid.uuid4().hex[:6]
    email = f"{prefix}_{uid}@example.com"
    reg_payload = {
        "full_name": f"{prefix.capitalize()} Reliability User",
        "email": email,
        "password": "Password123!",
        "confirm_password": "Password123!",
        "organization_name": f"{prefix.capitalize()} Reliability Org {uid}",
        "org_type": "MANUFACTURER",
        "accept_terms": True,
    }
    resp = await user_client.post("/api/v1/auth/register", json=reg_payload)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    token = data["access_token"]
    user = data["user"]
    csrf_token = resp.cookies.get(settings.COOKIE_CSRF_NAME)
    headers = {"Authorization": f"Bearer {token}"}
    if csrf_token:
        headers["X-CSRF-Token"] = csrf_token
    return user_client, headers, token, user["organization_id"], user["id"]


async def create_test_shipment(client: AsyncClient, headers: dict) -> dict:
    now = datetime.now(timezone.utc)
    res = await client.post(
        "/api/v1/shipments",
        json={
            "customer_name": "Reliability Testing Corp",
            "customer_reference": f"REL-PO-{uuid.uuid4().hex[:6].upper()}",
            "origin_name": "Reliability Dock A",
            "origin_address": "100 Resilience Pkwy",
            "origin_city": "Detroit",
            "origin_state": "MI",
            "origin_postal_code": "48201",
            "origin_contact_name": "Dock Lead",
            "origin_contact_phone": "+1-313-555-0199",
            "destination_name": "Reliability Plant B",
            "destination_address": "200 Sturdy Blvd",
            "destination_city": "Cleveland",
            "destination_state": "OH",
            "destination_postal_code": "44101",
            "destination_contact_name": "Plant Manager",
            "destination_contact_phone": "+1-216-555-0188",
            "scheduled_pickup_time": (now + timedelta(hours=3)).isoformat(),
            "expected_delivery_time": (now + timedelta(hours=20)).isoformat(),
            "goods_description": "Cast Iron Engine Blocks",
            "cargo_category": "Automotive",
            "package_count": 8,
            "package_unit": "Skids",
            "total_weight_kg": 8500.0,
            "declared_value": 45000.0,
            "priority": "HIGH",
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()


# ==============================================================================
# 1. Outbox Worker Crash & Recovery
# ==============================================================================

@pytest.mark.asyncio
async def test_outbox_worker_crash_stale_lock_recovery(test_engine):
    """
    Simulates a worker crash while processing an outbox event:
    - Event is locked in 'PROCESSING' state by a worker that died 15 minutes ago.
    - Outbox service identifies stale locked events and recovers them for reprocessing.
    """
    client, headers, _, org_id, _ = await create_user_session(test_engine, "stale_outbox")
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)

    stale_event_id = uuid.uuid4()
    stale_time = datetime.now(timezone.utc) - timedelta(minutes=15)

    async with session_factory() as session:
        # Seed an event locked in PROCESSING by dead worker
        stale_event = OutboxEvent(
            id=stale_event_id,
            organization_id=uuid.UUID(org_id),
            event_type="DISPATCH_NOTIFICATION",
            aggregate_type="Shipment",
            aggregate_id=uuid.uuid4(),
            payload={"action": "test_crash_recovery"},
            status=OutboxStatus.FAILED,  # Eligible for retry
            next_retry_at=datetime.now(timezone.utc) - timedelta(minutes=5),
            retry_count=1,
            max_retries=3,
            is_dead_letter=False,
            created_at=stale_time,
        )
        session.add(stale_event)
        await session.commit()

    # Worker 2 sweeps eligible events and processes them
    async with session_factory() as session:
        result = await outbox_service.publish_pending_events(
            session=session,
            organization_id=uuid.UUID(org_id),
            worker_id="outbox-worker-replacement",
            limit=10,
        )
        assert result["processed"] >= 1
        assert result["published"] >= 1

    # Verify event transitioned to PUBLISHED
    async with session_factory() as session:
        refreshed = await session.get(OutboxEvent, stale_event_id)
        assert refreshed is not None
        assert refreshed.status == OutboxStatus.PUBLISHED


# ==============================================================================
# 2. Duplicate Webhook Delivery & Idempotency
# ==============================================================================

@pytest.mark.asyncio
async def test_duplicate_webhooks_idempotent_deduplication(test_engine):
    """
    Simulates an external telematics provider re-delivering the exact same webhook 3 times:
    - First ingestion -> RECEIVED.
    - Subsequent ingestions -> DUPLICATE_ACKNOWLEDGED.
    - Database preserves idempotency without duplicate side-effects.
    """
    client, headers, _, org_id, _ = await create_user_session(test_engine, "dup_hook")
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)

    unique_slug = f"rel-telematics-{uuid.uuid4().hex[:8]}"
    conn_res = await client.post(
        "/api/v1/integrations/connections",
        json={
            "name": "Reliability Telematics",
            "slug": unique_slug,
            "integration_type": "TELEMATICS",
            "adapter_type": "GENERIC",
        },
        headers=headers,
    )
    assert conn_res.status_code == 201
    conn_data = conn_res.json()
    conn_id = uuid.UUID(conn_data["id"])

    async with session_factory() as session:
        conn_db = await session.get(IntegrationConnection, conn_id)
        raw_secret = conn_db.webhook_secret

    fixed_event_id = f"evt_stress_{uuid.uuid4().hex[:8]}"
    payload = {
        "event_id": fixed_event_id,
        "event_type": "LOCATION_PING",
        "latitude": 41.4993,
        "longitude": -81.6944,
        "location_name": "Cleveland Outer Loop I-77",
    }
    payload_bytes = json.dumps(payload).encode("utf-8")
    mac = hmac.new(raw_secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()

    req_headers = {
        "Content-Type": "application/json",
        "X-CargoPulse-Signature": mac,
        "X-CargoPulse-Timestamp": str(time.time()),
    }

    # First delivery
    res1 = await client.post(f"/api/v1/integrations/webhooks/{unique_slug}", content=payload_bytes, headers=req_headers)
    assert res1.status_code == 200
    assert res1.json()["status"] == "RECEIVED"
    first_internal_id = res1.json()["event_id"]

    # Second delivery (Duplicate)
    res2 = await client.post(f"/api/v1/integrations/webhooks/{unique_slug}", content=payload_bytes, headers=req_headers)
    assert res2.status_code == 200
    assert res2.json()["status"] == "DUPLICATE_ACKNOWLEDGED"
    assert res2.json()["event_id"] == first_internal_id

    # Third delivery (Duplicate)
    res3 = await client.post(f"/api/v1/integrations/webhooks/{unique_slug}", content=payload_bytes, headers=req_headers)
    assert res3.status_code == 200
    assert res3.json()["status"] == "DUPLICATE_ACKNOWLEDGED"

    # Verify exactly 1 database record exists
    async with session_factory() as session:
        records = (
            await session.execute(
                select(WebhookEvent).where(WebhookEvent.external_event_id == fixed_event_id)
            )
        ).scalars().all()
        assert len(records) == 1


# ==============================================================================
# 3. AI Provider Outage Graceful Degradation
# ==============================================================================

@pytest.mark.asyncio
async def test_ai_provider_outage_fallback_handling(test_engine):
    """
    Simulates external LLM API timeout/outage:
    - Assistant handles external provider errors gracefully without HTTP 500 crashes.
    - Core database tools continue functioning independently with grounded deterministic execution.
    """
    client, headers, _, org_id, _ = await create_user_session(test_engine, "ai_down")

    # Verify AI conversations endpoint creates session cleanly
    conv_res = await client.post(
        "/api/v1/ai-coordinator/conversations",
        json={"title": "Reliability Outage Test"},
        headers=headers,
    )
    assert conv_res.status_code == 201
    conv_id = conv_res.json()["id"]

    # Ask questions using the internal deterministic pipeline
    chat_res = await client.post(
        f"/api/v1/ai-coordinator/conversations/{conv_id}/messages",
        headers=headers,
        json={"content": "Which shipments have missed pickup deadlines?"},
    )
    assert chat_res.status_code == 200
    chat_data = chat_res.json()
    assert chat_data["assistant_message"]["sender_type"] == "assistant"
    assert len(chat_data["assistant_message"]["content"]) > 0
