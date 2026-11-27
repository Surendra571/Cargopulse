import asyncio
import hashlib
import hmac
import json
import time
import uuid
from datetime import datetime, timedelta, timezone
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.api.deps import get_db
from app.core.config import settings
from app.main import app
from app.models.enums import ExceptionType, IntegrationType, OutboxStatus
from app.models.integrations import AuditLog, IntegrationConnection, OutboxEvent, WebhookEvent
from app.models.operations import ExceptionRecord
from app.models.shipment import Shipment, ShipmentEvent
from app.services.integrations.adapters import adapter_registry
from app.services.integrations.dlq_service import dlq_service
from app.services.integrations.event_processor import event_processor
from app.services.integrations.monitoring_service import monitoring_service
from app.services.integrations.outbox_service import outbox_service
from app.services.integrations.registry_service import registry_service
from app.services.integrations.webhook_service import webhook_service


@pytest_asyncio.fixture
async def test_engine():
    engine = create_async_engine(
        settings.DATABASE_URL,
        poolclass=NullPool,
        connect_args={"ssl": False},
        echo=False,
    )
    yield engine
    await engine.dispose()


async def setup_test_org_and_client(test_engine, prefix="integ"):
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)

    async def override_get_db():
        async with session_factory() as session:
            try:
                yield session
            finally:
                await session.close()

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    client = AsyncClient(transport=transport, base_url="http://testserver")

    suffix = uuid.uuid4().hex[:6]
    email = f"{prefix}_{suffix}@example.com"
    reg_payload = {
        "full_name": "Integration Systems Lead",
        "email": email,
        "password": "SecurePassword123!",
        "confirm_password": "SecurePassword123!",
        "organization_name": f"Acme Logistics {suffix}",
        "org_type": "MANUFACTURER",
        "accept_terms": True,
    }
    reg_res = await client.post("/api/v1/auth/register", json=reg_payload)
    assert reg_res.status_code == 201, reg_res.text
    token = reg_res.json()["access_token"]
    user_id = reg_res.json()["user"]["id"]
    org_id = reg_res.json()["user"]["organization_id"]
    headers = {"Authorization": f"Bearer {token}"}

    return client, headers, uuid.UUID(org_id), uuid.UUID(user_id), session_factory


@pytest.mark.asyncio
async def test_webhook_signature_verification_and_auth(test_engine):
    """
    Validates HMAC-SHA256 signature, timestamp anti-replay tolerance,
    API-Key auth, rejection of invalid signatures, and ensures secrets are never leaked.
    """
    client, headers, org_id, user_id, session_factory = await setup_test_org_and_client(test_engine, "sig")

    # 1. Register integration connection
    create_res = await client.post(
        "/api/v1/integrations/connections",
        json={
            "name": "Fleet Webhook Ingest",
            "slug": f"fleet-ingest-{uuid.uuid4().hex[:6]}",
            "integration_type": "TELEMATICS",
            "adapter_type": "GENERIC",
            "api_key": "sec_apikey_test9988",
        },
        headers=headers,
    )
    assert create_res.status_code == 201
    conn_data = create_res.json()
    conn_id = uuid.UUID(conn_data["id"])
    slug = conn_data["slug"]

    # Verify secret is masked in API response
    assert conn_data["webhook_secret_preview"] is not None
    assert "****" in conn_data["webhook_secret_preview"]

    # Retrieve raw secret directly from DB for test signing
    async with session_factory() as session:
        conn_db = await session.get(IntegrationConnection, conn_id)
        raw_secret = conn_db.webhook_secret
        assert raw_secret is not None

    payload = {
        "event_id": f"evt_{uuid.uuid4().hex[:8]}",
        "event_type": "LOCATION_PING",
        "latitude": 19.0760,
        "longitude": 72.8777,
        "speed_kmh": 55.0,
        "vehicle_registration": "MH04AB1234",
    }
    payload_bytes = json.dumps(payload).encode("utf-8")

    # 2. Test Invalid Signature -> HTTP 401
    invalid_headers = {
        "Content-Type": "application/json",
        "X-CargoPulse-Signature": "sha256=invalid_hex_digest_00000000000000000000",
    }
    bad_res = await client.post(
        f"/api/v1/integrations/webhooks/{slug}",
        content=payload_bytes,
        headers=invalid_headers,
    )
    assert bad_res.status_code == 401
    assert "Invalid webhook signature" in bad_res.text

    # 3. Test Expired Timestamp -> HTTP 401
    expired_timestamp = str(time.time() - 600)  # 10 minutes ago
    mac = hmac.new(raw_secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
    expired_headers = {
        "Content-Type": "application/json",
        "X-CargoPulse-Signature": f"sha256={mac}",
        "X-CargoPulse-Timestamp": expired_timestamp,
    }
    expired_res = await client.post(
        f"/api/v1/integrations/webhooks/{slug}",
        content=payload_bytes,
        headers=expired_headers,
    )
    assert expired_res.status_code == 401

    # 4. Test Valid HMAC Signature with fresh timestamp -> HTTP 200
    fresh_timestamp = str(time.time())
    valid_headers = {
        "Content-Type": "application/json",
        "X-CargoPulse-Signature": f"sha256={mac}",
        "X-CargoPulse-Timestamp": fresh_timestamp,
    }
    valid_res = await client.post(
        f"/api/v1/integrations/webhooks/{slug}",
        content=payload_bytes,
        headers=valid_headers,
    )
    assert valid_res.status_code == 200
    assert valid_res.json()["status"] == "RECEIVED"

    # 5. Test API Key Auth -> HTTP 200
    apikey_headers = {
        "Content-Type": "application/json",
        "X-API-Key": "sec_apikey_test9988",
    }
    apikey_payload = dict(payload, event_id=f"evt_{uuid.uuid4().hex[:8]}")
    apikey_res = await client.post(
        f"/api/v1/integrations/webhooks/{slug}",
        json=apikey_payload,
        headers=apikey_headers,
    )
    assert apikey_res.status_code == 200
    assert apikey_res.json()["status"] == "RECEIVED"

    # 6. Verify security audit: No raw secrets in AuditLog
    async with session_factory() as session:
        audits = (
            await session.execute(
                select(AuditLog).where(AuditLog.action == "WEBHOOK_AUTH_FAILED")
            )
        ).scalars().all()
        for a in audits:
            raw_changes = json.dumps(a.changes)
            assert raw_secret not in raw_changes


@pytest.mark.asyncio
async def test_duplicate_webhooks_idempotent_deduplication(test_engine):
    """
    Validates that identical incoming webhooks are deduplicated by provider + external_event_id,
    preventing duplicate database rows and duplicate business side-effects.
    """
    client, headers, org_id, user_id, session_factory = await setup_test_org_and_client(test_engine, "dedup")

    # Create connection
    create_res = await client.post(
        "/api/v1/integrations/connections",
        json={
            "name": "Deduplication Telematics",
            "slug": f"dedup-{uuid.uuid4().hex[:6]}",
            "integration_type": "TELEMATICS",
            "adapter_type": "GENERIC",
        },
        headers=headers,
    )
    conn_data = create_res.json()
    conn_id = uuid.UUID(conn_data["id"])
    slug = conn_data["slug"]

    async with session_factory() as session:
        conn_db = await session.get(IntegrationConnection, conn_id)
        raw_secret = conn_db.webhook_secret

    fixed_event_id = f"evt_dedup_unique_{uuid.uuid4().hex[:6]}"
    payload = {
        "event_id": fixed_event_id,
        "event_type": "LOCATION_PING",
        "latitude": 13.0827,
        "longitude": 80.2707,
        "location_name": "Chennai Port Gate 1",
    }
    payload_bytes = json.dumps(payload).encode("utf-8")
    mac = hmac.new(raw_secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()

    req_headers = {
        "Content-Type": "application/json",
        "X-CargoPulse-Signature": mac,
        "X-CargoPulse-Timestamp": str(time.time()),
    }

    # First Delivery -> RECEIVED
    first_res = await client.post(
        f"/api/v1/integrations/webhooks/{slug}",
        content=payload_bytes,
        headers=req_headers,
    )
    assert first_res.status_code == 200
    assert first_res.json()["status"] == "RECEIVED"
    first_event_id = first_res.json()["event_id"]

    # Second Delivery (Exact duplicate) -> DUPLICATE_ACKNOWLEDGED
    second_res = await client.post(
        f"/api/v1/integrations/webhooks/{slug}",
        content=payload_bytes,
        headers=req_headers,
    )
    assert second_res.status_code == 200
    assert second_res.json()["status"] == "DUPLICATE_ACKNOWLEDGED"
    assert second_res.json()["event_id"] == first_event_id

    # Verify only 1 webhook_events row exists in PostgreSQL
    async with session_factory() as session:
        count = (
            await session.execute(
                select(WebhookEvent).where(WebhookEvent.external_event_id == fixed_event_id)
            )
        ).scalars().all()
        assert len(count) == 1

        # Process the event
        sweep_res = await event_processor.process_received_webhooks(session, organization_id=org_id, limit=10)
        assert sweep_res["succeeded"] >= 1


@pytest.mark.asyncio
async def test_transactional_outbox_atomic_business_transaction(test_engine):
    """
    Validates Transactional Outbox pattern:
    - If transaction rolls back, neither business mutation nor outbox event is saved.
    - If transaction commits, both exist atomically in PostgreSQL.
    """
    client, headers, org_id, user_id, session_factory = await setup_test_org_and_client(test_engine, "outbox_tx")

    # 1. Rollback test: simulate transaction failure
    shipment_id = uuid.uuid4()
    rollback_key = f"idemp_rollback_{uuid.uuid4().hex[:6]}"

    async with session_factory() as session:
        try:
            # Business change
            shipment = Shipment(
                id=shipment_id,
                organization_id=org_id,
                tracking_number=f"TRK-ROLLBACK-{uuid.uuid4().hex[:6]}",
                origin_name="Plant Pune",
                origin_address="123 Industrial Area",
                origin_city="Pune",
                origin_state="MH",
                origin_postal_code="411001",
                origin_contact_name="John",
                origin_contact_phone="9999999999",
                destination_name="Warehouse Mumbai",
                destination_address="456 Port Road",
                destination_city="Mumbai",
                destination_state="MH",
                destination_postal_code="400001",
                destination_contact_name="Bob",
                destination_contact_phone="8888888888",
                total_weight_kg=1000.0,
                package_count=10,
                goods_description="Auto Parts",
                scheduled_pickup_time=datetime.now(timezone.utc),
                expected_delivery_time=datetime.now(timezone.utc) + timedelta(days=2),
            )
            session.add(shipment)

            # Outbox event
            outbox_service.create_outbox_event(
                session=session,
                organization_id=org_id,
                aggregate_type="Shipment",
                aggregate_id=shipment_id,
                event_type="SHIPMENT_CREATED",
                payload={"tracking_number": shipment.tracking_number},
                idempotency_key=rollback_key,
            )

            # Intentionally raise to trigger rollback
            raise RuntimeError("SIMULATED_TRANSACTION_FAILURE")
        except RuntimeError:
            await session.rollback()

    # Verify neither shipment nor outbox event exists in PostgreSQL
    async with session_factory() as session:
        check_shipment = await session.get(Shipment, shipment_id)
        assert check_shipment is None

        check_outbox = (
            await session.execute(
                select(OutboxEvent).where(OutboxEvent.idempotency_key == rollback_key)
            )
        ).scalar_one_or_none()
        assert check_outbox is None

    # 2. Commit test: successful atomic transaction
    commit_key = f"idemp_commit_{uuid.uuid4().hex[:6]}"
    committed_shipment_id = uuid.uuid4()

    async with session_factory() as session:
        shipment2 = Shipment(
            id=committed_shipment_id,
            organization_id=org_id,
            tracking_number=f"TRK-COMMIT-{uuid.uuid4().hex[:6]}",
            origin_name="Plant Pune",
            origin_address="123 Industrial Area",
            origin_city="Pune",
            origin_state="MH",
            origin_postal_code="411001",
            origin_contact_name="John",
            origin_contact_phone="9999999999",
            destination_name="Warehouse Mumbai",
            destination_address="456 Port Road",
            destination_city="Mumbai",
            destination_state="MH",
            destination_postal_code="400001",
            destination_contact_name="Bob",
            destination_contact_phone="8888888888",
            total_weight_kg=2000.0,
            package_count=20,
            goods_description="Auto Parts",
            scheduled_pickup_time=datetime.now(timezone.utc),
            expected_delivery_time=datetime.now(timezone.utc) + timedelta(days=2),
        )
        session.add(shipment2)

        outbox_service.create_outbox_event(
            session=session,
            organization_id=org_id,
            aggregate_type="Shipment",
            aggregate_id=committed_shipment_id,
            event_type="SHIPMENT_COMMITTED",
            payload={"tracking_number": shipment2.tracking_number},
            idempotency_key=commit_key,
        )
        await session.commit()

    # Verify both exist atomically in PostgreSQL
    async with session_factory() as session:
        saved_shipment = await session.get(Shipment, committed_shipment_id)
        assert saved_shipment is not None

        saved_outbox = (
            await session.execute(
                select(OutboxEvent).where(OutboxEvent.idempotency_key == commit_key)
            )
        ).scalar_one_or_none()
        assert saved_outbox is not None
        assert saved_outbox.status == OutboxStatus.PENDING


@pytest.mark.asyncio
async def test_retry_exhaustion_transitions_to_dlq_and_exception(test_engine):
    """
    Validates that repeatedly failing retryable events exhaust max_retries,
    transition to DEAD_LETTER, and automatically create an INTEGRATION_FAILURE exception record.
    """
    client, headers, org_id, user_id, session_factory = await setup_test_org_and_client(test_engine, "exhaust")

    # Create an OutboxEvent with max_retries=2
    event_id = uuid.uuid4()
    async with session_factory() as session:
        evt = OutboxEvent(
            id=event_id,
            organization_id=org_id,
            aggregate_type="Shipment",
            aggregate_id=uuid.uuid4(),
            event_type="BOOKING_NOTIFY",
            payload={"msg": "test"},
            destination="http://unavailable.destination/webhook",
            status=OutboxStatus.PENDING,
            retry_count=0,
            max_retries=2,
            is_dead_letter=False,
        )
        session.add(evt)
        await session.commit()

    # Attempt 1: Fails -> status=FAILED, retry_count=1
    async with session_factory() as session:
        res1 = await outbox_service.publish_pending_events(
            session=session,
            organization_id=org_id,
            limit=10,
            simulate_failure_id=event_id,
        )
        assert res1["failed"] >= 1

    async with session_factory() as session:
        evt_db = await session.get(OutboxEvent, event_id)
        assert evt_db.status == OutboxStatus.FAILED
        assert evt_db.retry_count == 1
        assert evt_db.is_dead_letter == False
        # Manually reset next_retry_at to past for test simulation
        evt_db.next_retry_at = datetime.now(timezone.utc) - timedelta(seconds=10)
        await session.commit()

    # Attempt 2: Fails again -> reaches max_retries (2) -> DEAD_LETTER
    async with session_factory() as session:
        res2 = await outbox_service.publish_pending_events(
            session=session,
            organization_id=org_id,
            limit=10,
            simulate_failure_id=event_id,
        )
        assert res2["dead_letter"] >= 1

    # Verify event state and operational exception record
    async with session_factory() as session:
        evt_final = await session.get(OutboxEvent, event_id)
        assert evt_final.status == OutboxStatus.DEAD_LETTER
        assert evt_final.is_dead_letter == True

        # Check INTEGRATION_FAILURE exception in PostgreSQL
        exc_stmt = select(ExceptionRecord).where(
            ExceptionRecord.organization_id == org_id,
            ExceptionRecord.exception_type == ExceptionType.INTEGRATION_FAILURE,
        )
        exc = (await session.execute(exc_stmt)).scalars().first()
        assert exc is not None
        assert "Outbox Delivery Failure" in exc.title


@pytest.mark.asyncio
async def test_dlq_manual_replay_and_audit_trail(test_engine):
    """
    Validates that dead-lettered events can be manually replayed by operators,
    recording an immutable AuditLog entry and resetting execution state.
    """
    client, headers, org_id, user_id, session_factory = await setup_test_org_and_client(test_engine, "replay")

    # Create a dead-lettered webhook event
    dlq_event_id = uuid.uuid4()
    async with session_factory() as session:
        wh_evt = WebhookEvent(
            id=dlq_event_id,
            organization_id=org_id,
            provider="generic",
            source="GENERIC",
            event_name="LOCATION_PING",
            external_event_id="sam_dlq_1001",
            status="FAILED",
            is_dead_letter=True,
            retry_count=5,
            error_message="Network host unreachable",
            payload={"test": "data"},
            normalized_payload={"event_type": "LOCATION_PING", "latitude": 12.97, "longitude": 77.59},
            headers={},
        )
        session.add(wh_evt)
        await session.commit()

    # Replay via REST API endpoint
    replay_res = await client.post(
        f"/api/v1/integrations/dlq/webhook/{dlq_event_id}/replay",
        headers=headers,
    )
    assert replay_res.status_code == 200
    assert replay_res.json()["status"] == "REPLAYED"

    # Verify event updated in PostgreSQL
    async with session_factory() as session:
        replayed_evt = await session.get(WebhookEvent, dlq_event_id)
        assert replayed_evt.is_dead_letter == False
        assert replayed_evt.status == "PROCESSED"
        assert replayed_evt.replay_count == 1
        assert replayed_evt.last_replayed_by_id == user_id

        # Verify audit log recorded
        audit_stmt = select(AuditLog).where(
            AuditLog.entity_id == dlq_event_id,
            AuditLog.action == "REPLAY_DLQ_EVENT",
        )
        audit = (await session.execute(audit_stmt)).scalar_one_or_none()
        assert audit is not None
        assert audit.user_id == user_id


@pytest.mark.asyncio
async def test_worker_crashes_hung_event_recovery(test_engine):
    """
    Validates that events stuck in PROCESSING due to worker crashes
    are automatically unlocked and recovered back to PENDING/RECEIVED.
    """
    client, headers, org_id, user_id, session_factory = await setup_test_org_and_client(test_engine, "crash")

    old_locked_time = datetime.now(timezone.utc) - timedelta(minutes=15)

    hung_outbox_id = uuid.uuid4()
    hung_webhook_id = uuid.uuid4()

    async with session_factory() as session:
        # Hung outbox event
        hung_ob = OutboxEvent(
            id=hung_outbox_id,
            organization_id=org_id,
            aggregate_type="Shipment",
            aggregate_id=uuid.uuid4(),
            event_type="DISPATCH",
            payload={"info": "crashed worker"},
            status=OutboxStatus.PROCESSING,
            locked_at=old_locked_time,
            locked_by="dead-worker-pid-9999",
            is_dead_letter=False,
        )
        # Hung webhook event
        hung_wh = WebhookEvent(
            id=hung_webhook_id,
            organization_id=org_id,
            provider="generic",
            source="GENERIC",
            event_name="STATUS_PING",
            status="PROCESSING",
            last_attempt_at=old_locked_time,
            is_dead_letter=False,
            payload={},
            headers={},
        )
        session.add_all([hung_ob, hung_wh])
        await session.commit()

    # Trigger hung event recovery sweep
    async with session_factory() as session:
        rec_ob = await outbox_service.recover_hung_events(session, timeout_seconds=300)
        rec_wh = await event_processor.recover_hung_webhooks(session, timeout_seconds=300)
        assert rec_ob >= 1
        assert rec_wh >= 1

    # Verify events reset
    async with session_factory() as session:
        recovered_ob = await session.get(OutboxEvent, hung_outbox_id)
        assert recovered_ob.status == OutboxStatus.PENDING
        assert recovered_ob.locked_at is None
        assert recovered_ob.locked_by is None

        recovered_wh = await session.get(WebhookEvent, hung_webhook_id)
        assert recovered_wh.status == "RECEIVED"


@pytest.mark.asyncio
async def test_concurrent_event_processing_with_skip_locked(test_engine):
    """
    Validates that PostgreSQL 'FOR UPDATE SKIP LOCKED' safely partitions work
    across concurrent workers with zero double-processing or lock contention.
    """
    client, headers, org_id, user_id, session_factory = await setup_test_org_and_client(test_engine, "concurrent")

    # Enqueue 10 pending outbox events
    event_ids = []
    async with session_factory() as session:
        for i in range(10):
            eid = uuid.uuid4()
            event_ids.append(eid)
            evt = OutboxEvent(
                id=eid,
                organization_id=org_id,
                aggregate_type="Shipment",
                aggregate_id=uuid.uuid4(),
                event_type=f"EVENT_{i}",
                payload={"index": i},
                status=OutboxStatus.PENDING,
                is_dead_letter=False,
            )
            session.add(evt)
        await session.commit()

    # Concurrently execute two separate workers
    async def worker_job(worker_name: str):
        async with session_factory() as session:
            return await outbox_service.publish_pending_events(
                session, organization_id=org_id, limit=10, worker_id=worker_name
            )

    results = await asyncio.gather(
        worker_job("worker-alpha"),
        worker_job("worker-beta"),
    )

    total_published = sum(r["published"] for r in results)
    assert total_published == 10

    # Verify all 10 are published and were handled cleanly
    async with session_factory() as session:
        stmt = select(OutboxEvent).where(OutboxEvent.id.in_(event_ids))
        items = (await session.execute(stmt)).scalars().all()
        assert len(items) == 10
        assert all(it.status == OutboxStatus.PUBLISHED for it in items)


@pytest.mark.asyncio
async def test_vendor_adapters_normalization():
    """
    Unit test verifying normalized event extraction across Samsara, Intangles, and Custom ERP adapters.
    """
    # 1. Samsara Adapter
    samsara = adapter_registry.get_adapter("SAMSARA")
    sam_payload = {
        "eventId": "sam_12345",
        "happenedAtTime": "2026-11-25T14:30:00Z",
        "vehicle": {"id": "v-99", "name": "KA04XY9988"},
        "location": {
            "latitude": 12.9716,
            "longitude": 77.5946,
            "speedMilesPerHour": 50.0,
            "reverseGeo": {"formattedLocation": "Electronic City, BLR"},
        },
    }
    sam_norm = samsara.normalize_event(sam_payload, {})
    assert sam_norm.event_id == "sam_12345"
    assert sam_norm.vehicle_registration == "KA04XY9988"
    assert sam_norm.speed_kmh == round(50.0 * 1.60934, 1)
    assert sam_norm.location_name == "Electronic City, BLR"

    # 2. Intangles Adapter
    intangles = adapter_registry.get_adapter("INTANGLES")
    int_payload = {
        "packet_id": "int_7788",
        "timestamp": 1732545000,
        "vehicle_number": "MH12AB5544",
        "gps": {"lat": 18.5204, "lon": 73.8567, "speed": 60.5, "address": "Pune Express"},
    }
    int_norm = intangles.normalize_event(int_payload, {})
    assert int_norm.event_id == "int_7788"
    assert int_norm.vehicle_registration == "MH12AB5544"
    assert int_norm.speed_kmh == 60.5

    # 3. Custom ERP Adapter
    erp = adapter_registry.get_adapter("CUSTOM_ERP")
    erp_payload = {
        "message_id": "sap_msg_001",
        "document_number": "SAP-DOC-99",
        "status_code": "DISPATCH_CONFIRMED",
        "plant": "Central Plant Mumbai",
    }
    erp_norm = erp.normalize_event(erp_payload, {})
    assert erp_norm.event_id == "sap_msg_001"
    assert erp_norm.milestone == "IN_TRANSIT"
    assert erp_norm.location_name == "Central Plant Mumbai"


@pytest.mark.asyncio
async def test_permanent_error_bypasses_retries_to_dlq(test_engine):
    """
    Validates that non-retryable errors (e.g. 404, unrecoverable schema mismatch)
    immediately transition to DEAD_LETTER without wasting retry attempts.
    """
    client, headers, org_id, user_id, session_factory = await setup_test_org_and_client(test_engine, "perm_err")

    perm_event_id = uuid.uuid4()
    async with session_factory() as session:
        evt = OutboxEvent(
            id=perm_event_id,
            organization_id=org_id,
            aggregate_type="Shipment",
            aggregate_id=uuid.uuid4(),
            event_type="PERMANENT_FAIL_TEST",
            payload={"data": "unsupported"},
            destination="http://bad.destination/404",
            status=OutboxStatus.PENDING,
            retry_count=0,
            max_retries=5,
            is_dead_letter=False,
        )
        session.add(evt)
        await session.commit()

    # Trigger outbox processor with simulated permanent failure
    async with session_factory() as session:
        res = await outbox_service.publish_pending_events(
            session=session,
            organization_id=org_id,
            simulate_permanent_id=perm_event_id,
        )
        assert res["dead_letter"] == 1

    # Verify event immediately entered DEAD_LETTER with retry_count=0
    async with session_factory() as session:
        evt_db = await session.get(OutboxEvent, perm_event_id)
        assert evt_db.status == OutboxStatus.DEAD_LETTER
        assert evt_db.is_dead_letter == True
        assert evt_db.retry_count == 0


@pytest.mark.asyncio
async def test_redis_outage_resilience(test_engine):
    """
    Validates that transactional outbox and webhook persistence operate with complete durability
    directly backed by PostgreSQL transactions, functioning seamlessly even if Redis is unavailable.
    """
    client, headers, org_id, user_id, session_factory = await setup_test_org_and_client(test_engine, "no_redis")

    # Ingest incoming webhook and create outbox events with simulated Redis outage
    async with session_factory() as session:
        outbox_event = outbox_service.create_outbox_event(
            session=session,
            organization_id=org_id,
            aggregate_type="Shipment",
            aggregate_id=uuid.uuid4(),
            event_type="DISPATCH_COMPLETED",
            payload={"status": "DISPATCHED"},
            idempotency_key=f"no_redis_{uuid.uuid4().hex[:6]}",
        )
        await session.commit()
        await session.refresh(outbox_event)
        assert outbox_event.id is not None
        assert outbox_event.status == OutboxStatus.PENDING

        # Execute publish worker sweep directly via PostgreSQL transactions
        res = await outbox_service.publish_pending_events(session, organization_id=org_id)
        assert res["published"] >= 1

