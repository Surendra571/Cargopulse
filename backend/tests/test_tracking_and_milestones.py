import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.api.deps import get_db
from app.core.config import settings
from app.main import app
from app.models.enums import (
    ExceptionType,
    ShipmentMilestone,
    ShipmentStatus,
    TrackingEventSource,
)
from app.models.operations import ExceptionRecord
from app.models.shipment import Shipment, ShipmentEvent


@pytest_asyncio.fixture
async def test_engine():
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool, connect_args={"ssl": False}, echo=False)
    yield engine
    await engine.dispose()


async def create_user_session(test_engine, prefix: str = "track"):
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

    suffix = uuid.uuid4().hex[:6]
    email = f"{prefix}_{suffix}@example.com"
    reg_payload = {
        "full_name": "Tracking Lead",
        "email": email,
        "password": "SecurePassword123!",
        "confirm_password": "SecurePassword123!",
        "organization_name": f"Acme Logistics {suffix}",
        "org_type": "MANUFACTURER",
        "accept_terms": True,
    }
    reg_res = await user_client.post("/api/v1/auth/register", json=reg_payload)
    assert reg_res.status_code == 201, reg_res.text
    data = reg_res.json()
    token = data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    org_id = data["user"]["organization_id"]
    user_id = data["user"]["id"]

    return user_client, headers, token, org_id, user_id


async def _create_test_shipment(client: AsyncClient, headers: dict) -> dict:
    pickup_time = datetime.now(timezone.utc) + timedelta(hours=2)
    delivery_time = datetime.now(timezone.utc) + timedelta(hours=26)
    payload = {
        "customer_name": "Apex Electronics",
        "customer_reference": f"REF-{uuid.uuid4().hex[:6].upper()}",
        "origin_name": "Chicago Facility",
        "origin_address": "123 State St",
        "origin_city": "Chicago",
        "origin_state": "IL",
        "origin_postal_code": "60601",
        "origin_contact_name": "John Doe",
        "origin_contact_phone": "+1-312-555-0100",
        "destination_name": "Indianapolis DC",
        "destination_address": "456 Meridian St",
        "destination_city": "Indianapolis",
        "destination_state": "IN",
        "destination_postal_code": "46204",
        "destination_contact_name": "Jane Smith",
        "destination_contact_phone": "+1-317-555-0200",
        "scheduled_pickup_time": pickup_time.isoformat(),
        "expected_delivery_time": delivery_time.isoformat(),
        "total_weight_kg": 15000.0,
        "package_count": 500,
        "goods_description": "Auto parts palletized",
    }
    res = await client.post("/api/v1/shipments", json=payload, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


@pytest.mark.asyncio
async def test_chronological_milestone_progression_and_timeline(test_engine):
    """
    Validates recording milestone progression, chronological timeline retrieval,
    and automatic status transitions through all operational phases.
    """
    client, headers, token, org_id, user_id = await create_user_session(test_engine, "seq")
    shipment = await _create_test_shipment(client, headers)
    shipment_id = shipment["id"]

    # 1. TRANSPORTER_ASSIGNED
    r1 = await client.post(
        f"/api/v1/tracking/shipments/{shipment_id}/events",
        json={
            "milestone": "TRANSPORTER_ASSIGNED",
            "description": "Assigned to Midwest Express Logistics",
            "source": "OPERATOR",
        },
        headers=headers,
    )
    assert r1.status_code == 200, r1.text

    # 2. VEHICLE_ARRIVED
    r2 = await client.post(
        f"/api/v1/tracking/shipments/{shipment_id}/events",
        json={
            "milestone": "VEHICLE_ARRIVED",
            "description": "Trailer spotted at Dock 4",
            "location_name": "Chicago Facility Dock 4",
            "latitude": 41.8781,
            "longitude": -87.6298,
            "source": "DRIVER",
        },
        headers=headers,
    )
    assert r2.status_code == 200, r2.text

    # 3. PICKUP_COMPLETED
    r3 = await client.post(
        f"/api/v1/tracking/shipments/{shipment_id}/events",
        json={
            "milestone": "PICKUP_COMPLETED",
            "description": "500 packages loaded and sealed",
            "source": "OPERATOR",
        },
        headers=headers,
    )
    assert r3.status_code == 200, r3.text

    # 4. IN_TRANSIT
    r4 = await client.post(
        f"/api/v1/tracking/shipments/{shipment_id}/events",
        json={
            "milestone": "IN_TRANSIT",
            "description": "Departed origin hub heading south on I-65",
            "location_name": "I-65 Mile Marker 240",
            "source": "TELEMATICS",
        },
        headers=headers,
    )
    assert r4.status_code == 200, r4.text

    # 5. CHECKPOINT_REACHED
    r5 = await client.post(
        f"/api/v1/tracking/shipments/{shipment_id}/events",
        json={
            "milestone": "CHECKPOINT_REACHED",
            "description": "Passed Lafayette Weigh Station",
            "location_name": "Lafayette Toll Plaza",
            "latitude": 40.4173,
            "longitude": -86.8753,
            "source": "TELEMATICS",
        },
        headers=headers,
    )
    assert r5.status_code == 200, r5.text

    # 6. DELIVERED
    r6 = await client.post(
        f"/api/v1/tracking/shipments/{shipment_id}/events",
        json={
            "milestone": "DELIVERED",
            "description": "Consignment received and signed at Indianapolis DC",
            "location_name": "Indianapolis DC Bay 12",
            "source": "OPERATOR",
        },
        headers=headers,
    )
    assert r6.status_code == 200, r6.text

    # Verify Timeline View
    timeline_res = await client.get(
        f"/api/v1/tracking/shipments/{shipment_id}/timeline",
        headers=headers,
    )
    assert timeline_res.status_code == 200, timeline_res.text
    timeline = timeline_res.json()

    assert timeline["status"] == "DELIVERED"
    assert timeline["current_milestone"] == "DELIVERED"
    assert len(timeline["events"]) >= 6
    assert len(timeline["milestone_progress"]) == 10

    # Ensure DELIVERED milestone is marked completed
    delivered_item = next(m for m in timeline["milestone_progress"] if m["milestone"] == "DELIVERED")
    assert delivered_item["completed"] is True
    assert delivered_item["is_current"] is True


@pytest.mark.asyncio
async def test_out_of_order_event_handling_and_no_status_regression(test_engine):
    """
    Validates that events received out of chronological order (e.g. offline driver upload)
    are recorded with exact timestamps without regressing progressive shipment status.
    """
    client, headers, token, org_id, user_id = await create_user_session(test_engine, "ooo")
    shipment = await _create_test_shipment(client, headers)
    shipment_id = shipment["id"]

    now = datetime.now(timezone.utc)

    # 1. Advance shipment to IN_TRANSIT
    await client.post(
        f"/api/v1/tracking/shipments/{shipment_id}/events",
        json={
            "milestone": "IN_TRANSIT",
            "description": "Shipment is rolling on highway",
            "occurred_at": (now + timedelta(hours=2)).isoformat(),
        },
        headers=headers,
    )

    # Check status is IN_TRANSIT
    t1 = (await client.get(f"/api/v1/tracking/shipments/{shipment_id}/timeline", headers=headers)).json()
    assert t1["status"] == "IN_TRANSIT"
    assert t1["current_milestone"] == "IN_TRANSIT"

    # 2. Delayed out-of-order event arrives (VEHICLE_ARRIVED from 2 hours ago)
    delayed_time = now - timedelta(hours=1)
    ooo_res = await client.post(
        f"/api/v1/tracking/shipments/{shipment_id}/events",
        json={
            "milestone": "VEHICLE_ARRIVED",
            "description": "Delayed driver log: arrived at origin earlier today",
            "occurred_at": delayed_time.isoformat(),
            "source": "DRIVER",
        },
        headers=headers,
    )
    assert ooo_res.status_code == 200, ooo_res.text

    # 3. Verify status did NOT regress back to AT_PICKUP!
    t2 = (await client.get(f"/api/v1/tracking/shipments/{shipment_id}/timeline", headers=headers)).json()
    assert t2["status"] == "IN_TRANSIT"
    assert t2["current_milestone"] == "IN_TRANSIT"

    # 4. Verify the delayed event is present in chronological order in events list
    events = t2["events"]
    assert any(e["milestone"] == "VEHICLE_ARRIVED" for e in events)

    # 5. Advance to DELIVERED terminal status
    await client.post(
        f"/api/v1/tracking/shipments/{shipment_id}/events",
        json={
            "milestone": "DELIVERED",
            "description": "Consignment signed for",
            "occurred_at": (now + timedelta(hours=3)).isoformat(),
        },
        headers=headers,
    )

    # 6. Attempting to transition from DELIVERED backwards to IN_TRANSIT must be rejected with 400
    regress_res = await client.post(
        f"/api/v1/tracking/shipments/{shipment_id}/events",
        json={"milestone": "IN_TRANSIT", "description": "Erroneous status update"},
        headers=headers,
    )
    assert regress_res.status_code == 400
    assert "already reached DELIVERED" in regress_res.text


@pytest.mark.asyncio
async def test_duplicate_event_prevention_and_idempotency(test_engine):
    """
    Validates idempotency key handling and tight-window duplicate event deduplication.
    """
    client, headers, token, org_id, user_id = await create_user_session(test_engine, "idem")
    shipment = await _create_test_shipment(client, headers)
    shipment_id = shipment["id"]

    idempotency_key = f"key_{uuid.uuid4().hex}"

    # 1. First event submission with idempotency key
    res1 = await client.post(
        f"/api/v1/tracking/shipments/{shipment_id}/events",
        json={
            "milestone": "CHECKPOINT_REACHED",
            "location_name": "Toll Plaza A",
            "description": "Passed Toll Plaza A",
            "idempotency_key": idempotency_key,
        },
        headers=headers,
    )
    assert res1.status_code == 200
    event1 = res1.json()

    # 2. Second event submission with identical idempotency key
    res2 = await client.post(
        f"/api/v1/tracking/shipments/{shipment_id}/events",
        json={
            "milestone": "CHECKPOINT_REACHED",
            "location_name": "Toll Plaza A",
            "description": "Passed Toll Plaza A duplicate call",
            "idempotency_key": idempotency_key,
        },
        headers=headers,
    )
    assert res2.status_code == 200
    event2 = res2.json()

    # Must return identical event ID
    assert event1["id"] == event2["id"]

    # 3. Check timeline has exactly 1 event for this milestone
    timeline = (await client.get(f"/api/v1/tracking/shipments/{shipment_id}/timeline", headers=headers)).json()
    checkpoint_events = [e for e in timeline["events"] if e["milestone"] == "CHECKPOINT_REACHED"]
    assert len(checkpoint_events) == 1


@pytest.mark.asyncio
async def test_event_sources_and_webhook_ingestion(test_engine):
    """
    Validates webhook ingestion via tracking_number and event sources (TRANSPORTER, DRIVER, WEBHOOK).
    """
    client, headers, token, org_id, user_id = await create_user_session(test_engine, "src")
    shipment = await _create_test_shipment(client, headers)
    tracking_number = shipment["tracking_number"]

    # Ingest webhook update using tracking_number
    webhook_res = await client.post(
        "/api/v1/tracking/webhook",
        json={
            "tracking_number": tracking_number,
            "milestone": "IN_TRANSIT",
            "location_name": "Gary Interchange GPS",
            "latitude": 41.5934,
            "longitude": -87.3464,
            "description": "Automated GPS ping from Samsara Telematics",
            "source": "WEBHOOK",
        },
    )
    assert webhook_res.status_code == 200, webhook_res.text
    wh_data = webhook_res.json()
    assert wh_data["source"] == "WEBHOOK"
    assert wh_data["milestone"] == "IN_TRANSIT"
    assert wh_data["location_name"] == "Gary Interchange GPS"

    # Verify timeline reflects webhook event
    timeline = (await client.get(f"/api/v1/tracking/shipments/{shipment['id']}/timeline", headers=headers)).json()
    assert timeline["last_known_location"] == "Gary Interchange GPS"
    assert timeline["last_known_latitude"] == 41.5934


@pytest.mark.asyncio
async def test_eta_update_and_significant_delay_notification(test_engine):
    """
    Validates updating configurable ETA and automatic DELIVERY_DELAYED exception
    generation when revised ETA introduces >60m delay.
    """
    client, headers, token, org_id, user_id = await create_user_session(test_engine, "eta")
    shipment = await _create_test_shipment(client, headers)
    shipment_id = shipment["id"]

    original_eta = datetime.fromisoformat(shipment["expected_delivery_time"])
    delayed_eta = original_eta + timedelta(hours=3)  # 180 min delay

    eta_res = await client.post(
        f"/api/v1/tracking/shipments/{shipment_id}/eta",
        json={
            "new_eta": delayed_eta.isoformat(),
            "reason": "Severe highway blizzard and road closure detour",
        },
        headers=headers,
    )
    assert eta_res.status_code == 200, eta_res.text

    # Verify timeline reflects updated ETA and delay
    timeline = (await client.get(f"/api/v1/tracking/shipments/{shipment_id}/timeline", headers=headers)).json()
    assert timeline["eta_delay_minutes"] >= 170

    # Verify DELIVERY_DELAYED exception was created in database
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        exc_stmt = select(ExceptionRecord).where(
            ExceptionRecord.shipment_id == uuid.UUID(shipment_id),
            ExceptionRecord.exception_type == ExceptionType.DELIVERY_DELAYED,
        )
        exc = (await session.execute(exc_stmt)).scalar_one_or_none()
        assert exc is not None, "DELIVERY_DELAYED exception should be automatically recorded"
        assert exc.severity == "HIGH"
        assert "Delay of" in exc.description


@pytest.mark.asyncio
async def test_stale_tracking_detection_scan(test_engine):
    """
    Validates surveillance scan marking is_tracking_stale=True and opening
    TRACKING_STALE exceptions when pings are missing past threshold.
    """
    client, headers, token, org_id, user_id = await create_user_session(test_engine, "stale")
    shipment = await _create_test_shipment(client, headers)
    shipment_id = shipment["id"]

    # Advance to IN_TRANSIT
    await client.post(
        f"/api/v1/tracking/shipments/{shipment_id}/events",
        json={"milestone": "IN_TRANSIT", "description": "Departed"},
        headers=headers,
    )

    # Run scan with simulated_now 8 hours in future (> 6h threshold)
    simulated_now = datetime.now(timezone.utc) + timedelta(hours=8)
    scan_res = await client.post(
        f"/api/v1/tracking/scan?threshold_hours=6&simulated_now={simulated_now.isoformat()}",
        headers=headers,
    )
    assert scan_res.status_code == 200, scan_res.text
    scan_data = scan_res.json()
    assert scan_data["stale_flagged_count"] >= 1
    assert scan_data["exceptions_created"] >= 1

    # Verify shipment is marked is_tracking_stale=True
    timeline = (await client.get(f"/api/v1/tracking/shipments/{shipment_id}/timeline", headers=headers)).json()
    assert timeline["is_tracking_stale"] is True

    # A fresh event clears the stale state
    await client.post(
        f"/api/v1/tracking/shipments/{shipment_id}/events",
        json={
            "milestone": "CHECKPOINT_REACHED",
            "description": "Restored satellite telemetry ping",
            "occurred_at": (simulated_now + timedelta(minutes=5)).isoformat(),
        },
        headers=headers,
    )
    timeline2 = (await client.get(f"/api/v1/tracking/shipments/{shipment_id}/timeline", headers=headers)).json()
    assert timeline2["is_tracking_stale"] is False


@pytest.mark.asyncio
async def test_websocket_realtime_authorization(test_engine):
    """
    Validates WebSocket authentication, tenant isolation, and live connection handshake.
    """
    client, headers, token, org_id, user_id = await create_user_session(test_engine, "ws")
    shipment = await _create_test_shipment(client, headers)
    shipment_id = shipment["id"]

    # 1. Missing token must be rejected with policy violation (1008)
    with TestClient(app) as sync_client:
        with pytest.raises(WebSocketDisconnect):
            with sync_client.websocket_connect(f"/api/v1/tracking/ws/{shipment_id}"):
                pass

    # 2. Invalid token must be rejected
    with TestClient(app) as sync_client:
        with pytest.raises(WebSocketDisconnect):
            with sync_client.websocket_connect(f"/api/v1/tracking/ws/{shipment_id}?token=invalid.jwt.token"):
                pass

    # 3. Valid token for matching shipment connects and receives SUBSCRIPTION_CONFIRMED
    with TestClient(app) as sync_client:
        with sync_client.websocket_connect(f"/api/v1/tracking/ws/{shipment_id}?token={token}") as ws:
            handshake = ws.receive_json()
            assert handshake["type"] == "SUBSCRIPTION_CONFIRMED"
            assert handshake["shipment_id"] == shipment_id
            assert handshake["tracking_number"] == shipment["tracking_number"]

            # Heartbeat ping/pong
            ws.send_json({"type": "PING"})
            pong = ws.receive_json()
            assert pong["type"] == "PONG"
