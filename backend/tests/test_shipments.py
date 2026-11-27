import uuid
from datetime import datetime, timedelta, timezone
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.api.deps import get_db
from app.core.config import settings
from app.main import app
from app.models.enums import ShipmentStatus
from app.models.shipment import Shipment


@pytest_asyncio.fixture
async def test_engine():
    """Async engine using NullPool to prevent event loop connection leakage across tests."""
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool, connect_args={"ssl": False}, echo=False)
    yield engine
    await engine.dispose()


async def create_user_session(test_engine, prefix: str):
    """Helper to create an isolated HTTP client and authenticated user."""
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
        "full_name": f"{prefix.capitalize()} Admin",
        "email": email,
        "password": "Password123!",
        "confirm_password": "Password123!",
        "organization_name": f"{prefix.capitalize()} Logistics {uid}",
        "org_type": "MANUFACTURER",
        "accept_terms": True,
    }
    resp = await user_client.post("/api/v1/auth/register", json=reg_payload)
    assert resp.status_code == 201
    data = resp.json()
    token = data["access_token"]
    user = data["user"]
    csrf_token = resp.cookies.get(settings.COOKIE_CSRF_NAME)
    headers = {"Authorization": f"Bearer {token}"}
    if csrf_token:
        headers["X-CSRF-Token"] = csrf_token
    return user_client, user, headers, email


def sample_shipment_payload(now: datetime = None) -> dict:
    if not now:
        now = datetime.now(timezone.utc)
    pickup_time = (now + timedelta(days=1)).isoformat()
    delivery_time = (now + timedelta(days=3)).isoformat()

    return {
        "customer_name": "Apex Auto Components Ltd",
        "customer_reference": "PO-2026-9901",
        "origin_name": "Acme Central Plant",
        "origin_address": "100 Industrial Parkway",
        "origin_city": "Detroit",
        "origin_state": "MI",
        "origin_postal_code": "48201",
        "origin_dock_number": "Dock 4B",
        "origin_contact_name": "Marcus Vance",
        "origin_contact_phone": "+1-313-555-0199",
        "destination_name": "Apex Distribution Center",
        "destination_address": "450 Logistics Way",
        "destination_city": "Cleveland",
        "destination_state": "OH",
        "destination_postal_code": "44101",
        "destination_dock_number": "Receiving Bay 2",
        "destination_contact_name": "Elena Rostova",
        "destination_contact_phone": "+1-216-555-0144",
        "goods_description": "Precision Machined Transmission Housings",
        "cargo_category": "AUTOMOTIVE",
        "total_weight_kg": 4500.0,
        "package_count": 8,
        "package_unit": "PALLETS",
        "total_volume_cbm": 14.5,
        "required_vehicle_type": "53' Dry Van",
        "is_hazardous": False,
        "scheduled_pickup_time": pickup_time,
        "expected_delivery_time": delivery_time,
        "priority": "EXPEDITED",
        "special_instructions": "Must be strapped securely. No double-stacking.",
        "invoice_number": "INV-2026-0881",
        "invoice_value": 78500.0,
    }


@pytest.mark.asyncio
async def test_create_shipment_success(test_engine):
    """Verify successful shipment creation, tracking number generation, and event logging."""
    client, user, headers, _ = await create_user_session(test_engine, "create_shp")
    payload = sample_shipment_payload()

    resp = await client.post("/api/v1/shipments", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    data = resp.json()

    assert data["id"] is not None
    assert data["tracking_number"].startswith(f"SHP-{datetime.now(timezone.utc).year}-")
    assert data["status"] == "DRAFT"
    assert data["customer_name"] == "Apex Auto Components Ltd"
    assert data["total_weight_kg"] == 4500.0
    assert data["package_count"] == 8
    assert data["priority"] == "EXPEDITED"
    assert len(data["events"]) >= 1
    assert data["events"][0]["event_type"] == "SHIPMENT_CREATED"
    assert len(data["audit_history"]) >= 1
    assert data["audit_history"][0]["action"] == "CREATE"


@pytest.mark.asyncio
async def test_create_shipment_validation_negative_weight(test_engine):
    """Verify validation rejection of negative or zero cargo weight."""
    client, user, headers, _ = await create_user_session(test_engine, "neg_weight")
    payload = sample_shipment_payload()
    payload["total_weight_kg"] = -10.0

    resp = await client.post("/api/v1/shipments", json=payload, headers=headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_shipment_validation_delivery_before_pickup(test_engine):
    """Verify validation rejection when expected delivery is before or equal to pickup."""
    client, user, headers, _ = await create_user_session(test_engine, "bad_dates")
    now = datetime.now(timezone.utc)
    payload = sample_shipment_payload(now)
    # Set delivery earlier than pickup
    payload["scheduled_pickup_time"] = (now + timedelta(days=2)).isoformat()
    payload["expected_delivery_time"] = (now + timedelta(days=1)).isoformat()

    resp = await client.post("/api/v1/shipments", json=payload, headers=headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_shipments_with_filters_and_pagination(test_engine):
    """Verify shipment listing, searching, status/priority filtering, and pagination."""
    client, user, headers, _ = await create_user_session(test_engine, "list_shp")

    # Create 3 shipments with different priorities
    p1 = sample_shipment_payload()
    p1["priority"] = "STANDARD"
    p1["goods_description"] = "Industrial Fasteners"
    await client.post("/api/v1/shipments", json=p1, headers=headers)

    p2 = sample_shipment_payload()
    p2["priority"] = "CRITICAL"
    p2["goods_description"] = "Robotic Arm Subassemblies"
    await client.post("/api/v1/shipments", json=p2, headers=headers)

    p3 = sample_shipment_payload()
    p3["priority"] = "EXPEDITED"
    p3["goods_description"] = "Hydraulic Valves"
    await client.post("/api/v1/shipments", json=p3, headers=headers)

    # 1. Basic listing
    resp = await client.get("/api/v1/shipments?page=1&page_size=10", headers=headers)
    assert resp.status_code == 200
    res = resp.json()
    assert res["total"] == 3
    assert len(res["items"]) == 3

    # 2. Filter by priority
    resp_crit = await client.get("/api/v1/shipments?priority=CRITICAL", headers=headers)
    assert resp_crit.status_code == 200
    assert resp_crit.json()["total"] == 1
    assert resp_crit.json()["items"][0]["priority"] == "CRITICAL"

    # 3. Search by goods description
    resp_search = await client.get("/api/v1/shipments?search=Fasteners", headers=headers)
    assert resp_search.status_code == 200
    assert resp_search.json()["total"] == 1
    assert "Fasteners" in resp_search.json()["items"][0]["goods_description"]


@pytest.mark.asyncio
async def test_get_shipment_detail(test_engine):
    """Verify retrieving complete shipment details by ID."""
    client, user, headers, _ = await create_user_session(test_engine, "get_shp")
    payload = sample_shipment_payload()
    create_resp = await client.post("/api/v1/shipments", json=payload, headers=headers)
    shipment_id = create_resp.json()["id"]

    resp = await client.get(f"/api/v1/shipments/{shipment_id}", headers=headers)
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["id"] == shipment_id
    assert detail["origin_city"] == "Detroit"
    assert detail["destination_city"] == "Cleveland"
    assert "events" in detail
    assert "audit_history" in detail


@pytest.mark.asyncio
async def test_update_eligible_shipment(test_engine):
    """Verify updating shipment attributes while in draft status."""
    client, user, headers, _ = await create_user_session(test_engine, "update_shp")
    payload = sample_shipment_payload()
    create_resp = await client.post("/api/v1/shipments", json=payload, headers=headers)
    shipment_id = create_resp.json()["id"]

    update_payload = {
        "goods_description": "Updated Precision Housings & Brackets",
        "total_weight_kg": 5200.0,
        "special_instructions": "Fragile components. Temperature controlled transport.",
    }
    resp = await client.put(f"/api/v1/shipments/{shipment_id}", json=update_payload, headers=headers)
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["goods_description"] == "Updated Precision Housings & Brackets"
    assert updated["total_weight_kg"] == 5200.0
    assert updated["special_instructions"] == "Fragile components. Temperature controlled transport."

    # Audit log should have UPDATE entry
    actions = [log["action"] for log in updated["audit_history"]]
    assert "UPDATE" in actions


@pytest.mark.asyncio
async def test_update_shipment_locked_after_dispatch(test_engine):
    """Verify that routing, cargo specs, and dates cannot be modified after dispatch."""
    client, user, headers, _ = await create_user_session(test_engine, "locked_shp")
    payload = sample_shipment_payload()
    create_resp = await client.post("/api/v1/shipments", json=payload, headers=headers)
    shipment_id = create_resp.json()["id"]

    # Directly set shipment to DISPATCHED in the database
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        await session.execute(
            update(Shipment)
            .where(Shipment.id == uuid.UUID(shipment_id))
            .values(status=ShipmentStatus.DISPATCHED.value)
        )
        await session.commit()

    # Attempt to change origin and weight (should fail with 400)
    update_payload = {
        "origin_address": "999 Rogue Street",
        "total_weight_kg": 10000.0,
    }
    resp = await client.put(f"/api/v1/shipments/{shipment_id}", json=update_payload, headers=headers)
    assert resp.status_code == 400
    assert "cannot be modified after shipment has been dispatched" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_cancel_shipment_and_prevent_delivered_cancellation(test_engine):
    """Verify cancelling a draft shipment succeeds, but cancelling a delivered shipment fails."""
    client, user, headers, _ = await create_user_session(test_engine, "cancel_shp")
    payload = sample_shipment_payload()
    create_resp = await client.post("/api/v1/shipments", json=payload, headers=headers)
    shipment_id = create_resp.json()["id"]

    # Cancel draft shipment
    cancel_payload = {"cancellation_reason": "Order cancelled by customer due to production delay."}
    resp = await client.post(f"/api/v1/shipments/{shipment_id}/cancel", json=cancel_payload, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "CANCELLED"

    # Verify event logged
    events = [e["event_type"] for e in resp.json()["events"]]
    assert "SHIPMENT_CANCELLED" in events

    # Cannot cancel already cancelled shipment
    resp_again = await client.post(f"/api/v1/shipments/{shipment_id}/cancel", json=cancel_payload, headers=headers)
    assert resp_again.status_code == 400

    # Create another shipment and mark it DELIVERED
    resp2 = await client.post("/api/v1/shipments", json=payload, headers=headers)
    shipment_id_2 = resp2.json()["id"]
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        await session.execute(
            update(Shipment)
            .where(Shipment.id == uuid.UUID(shipment_id_2))
            .values(status=ShipmentStatus.DELIVERED.value)
        )
        await session.commit()

    # Attempt to cancel delivered shipment
    resp_deliv = await client.post(f"/api/v1/shipments/{shipment_id_2}/cancel", json=cancel_payload, headers=headers)
    assert resp_deliv.status_code == 400
    assert "Delivered shipments cannot be cancelled" in resp_deliv.json()["detail"]


@pytest.mark.asyncio
async def test_tenant_isolation_idor_protection(test_engine):
    """Verify Tenant B cannot view, edit, or cancel shipments belonging to Tenant A."""
    client_a, _, headers_a, _ = await create_user_session(test_engine, "tenant_a")
    client_b, _, headers_b, _ = await create_user_session(test_engine, "tenant_b")

    # Tenant A creates shipment
    payload = sample_shipment_payload()
    create_resp = await client_a.post("/api/v1/shipments", json=payload, headers=headers_a)
    assert create_resp.status_code == 201
    shipment_id = create_resp.json()["id"]

    # Tenant B tries to get Tenant A's shipment -> 404
    resp_get = await client_b.get(f"/api/v1/shipments/{shipment_id}", headers=headers_b)
    assert resp_get.status_code == 404

    # Tenant B tries to update Tenant A's shipment -> 404
    resp_put = await client_b.put(
        f"/api/v1/shipments/{shipment_id}",
        json={"goods_description": "Hacked goods"},
        headers=headers_b,
    )
    assert resp_put.status_code == 404

    # Tenant B tries to cancel Tenant A's shipment -> 404
    resp_cancel = await client_b.post(
        f"/api/v1/shipments/{shipment_id}/cancel",
        json={"cancellation_reason": "Malicious cancellation attempt"},
        headers=headers_b,
    )
    assert resp_cancel.status_code == 404
