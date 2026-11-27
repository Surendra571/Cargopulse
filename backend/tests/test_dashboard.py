import uuid
from datetime import datetime, timezone
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.api.deps import get_db
from app.core.config import settings
from app.main import app


@pytest_asyncio.fixture
async def test_engine():
    """Async engine using NullPool to prevent event loop connection leakage across tests."""
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool, echo=False)
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
        "organization_name": f"{prefix.capitalize()} Enterprise {uid}",
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


async def login_user(test_engine, email: str, password: str = "Password123!"):
    """Helper to login an existing user."""
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

    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    data = resp.json()
    token = data["access_token"]
    user = data["user"]
    csrf_token = resp.cookies.get(settings.COOKIE_CSRF_NAME)
    headers = {"Authorization": f"Bearer {token}"}
    if csrf_token:
        headers["X-CSRF-Token"] = csrf_token
    return client, user, headers


@pytest.mark.asyncio
async def test_empty_dashboard_metrics(test_engine):
    """
    Verifies that a brand-new organization with zero shipments receives
    clean zeroed metrics and empty tables without errors.
    """
    client, user, headers, _ = await create_user_session(test_engine, "zero_data")
    try:
        # 1. Query Dashboard Overview
        res = await client.get("/api/v1/dashboard/overview", headers=headers)
        assert res.status_code == 200
        data = res.json()

        metrics = data["metrics"]
        assert metrics["total_shipments"] == 0
        assert metrics["pending_pickups"] == 0
        assert metrics["confirmed_bookings"] == 0
        assert metrics["pickups_at_risk"] == 0
        assert metrics["failed_pickups"] == 0
        assert metrics["in_transit_shipments"] == 0
        assert metrics["delayed_deliveries"] == 0
        assert metrics["delivered_shipments"] == 0
        assert metrics["open_exceptions"] == 0
        assert metrics["pickup_success_rate"] == 0.0
        assert metrics["on_time_delivery_rate"] == 0.0

        # Arrays should be clean
        assert isinstance(data["volume_over_time"], list)
        assert data["transporter_rankings"] == []
        assert data["exceptions_by_type"] == []
        assert data["exceptions_by_severity"] == []
        assert data["recent_activity"] == []

        # 2. Query Tables
        table_res = await client.get("/api/v1/dashboard/tables/attention", headers=headers)
        assert table_res.status_code == 200
        assert table_res.json()["total"] == 0
        assert table_res.json()["items"] == []
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_dashboard_overview_metrics_accuracy(test_engine):
    """
    Logs in with the seeded Acme tenant and validates accuracy of all
    aggregated metrics, volume points, carrier rankings, and recent activities.
    """
    client, user, headers = await login_user(test_engine, "ops.lead@acme-mfg.com", "Password123!")
    try:
        # Query Overview
        res = await client.get("/api/v1/dashboard/overview", headers=headers)
        assert res.status_code == 200
        data = res.json()

        metrics = data["metrics"]
        assert metrics["total_shipments"] >= 25
        assert metrics["delivered_shipments"] >= 10
        assert metrics["in_transit_shipments"] >= 6
        assert metrics["failed_pickups"] >= 2
        assert metrics["open_exceptions"] >= 3
        assert metrics["pickup_success_rate"] > 0
        assert metrics["on_time_delivery_rate"] > 0

        # Volume over time should contain points
        assert len(data["volume_over_time"]) >= 7

        # Transporter rankings should list the 4 seeded carriers
        rankings = data["transporter_rankings"]
        assert len(rankings) >= 4
        codes = [r["transporter_code"] for r in rankings]
        assert "APEX" in codes
        assert "VNGD" in codes
        assert "BLST" in codes
        assert "TITN" in codes

        # Exceptions distributions
        assert len(data["exceptions_by_type"]) >= 2
        assert len(data["exceptions_by_severity"]) >= 2

        # Recent activities
        assert len(data["recent_activity"]) > 0
        first_event = data["recent_activity"][0]
        assert "tracking_number" in first_event
        assert "event_type" in first_event
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_dashboard_tables_and_filtering(test_engine):
    """
    Tests pagination and searching on dashboard tables.
    """
    client, user, headers = await login_user(test_engine, "ops.lead@acme-mfg.com", "Password123!")
    try:
        # 1. Attention Table
        res_attn = await client.get("/api/v1/dashboard/tables/attention", headers=headers)
        assert res_attn.status_code == 200
        data_attn = res_attn.json()
        assert data_attn["total"] >= 3
        for item in data_attn["items"]:
            assert item["is_at_risk"] or item["status"] in ["EXCEPTION", "IN_TRANSIT", "OUT_FOR_DELIVERY"] or item["open_exceptions_count"] > 0

        # 2. Upcoming Pickups Table
        res_pk = await client.get("/api/v1/dashboard/tables/upcoming-pickups", headers=headers)
        assert res_pk.status_code == 200
        data_pk = res_pk.json()
        assert data_pk["total"] >= 4
        for item in data_pk["items"]:
            assert item["actual_pickup_time"] is None

        # 3. Deliveries Table with Pagination
        res_deliv = await client.get("/api/v1/dashboard/tables/deliveries?page=1&page_size=5", headers=headers)
        assert res_deliv.status_code == 200
        data_deliv = res_deliv.json()
        assert len(data_deliv["items"]) == 5
        assert data_deliv["total_pages"] >= 2

        # 4. Search Filter
        res_search = await client.get("/api/v1/dashboard/tables/deliveries?search=SHP-2026-9001", headers=headers)
        assert res_search.status_code == 200
        data_search = res_search.json()
        assert data_search["total"] == 1
        assert data_search["items"][0]["tracking_number"] == "SHP-2026-9001"

        # 5. Open Exceptions Table
        res_exc = await client.get("/api/v1/dashboard/tables/exceptions", headers=headers)
        assert res_exc.status_code == 200
        data_exc = res_exc.json()
        assert data_exc["total"] >= 3
        titles = [e["title"] for e in data_exc["items"]]
        assert any("Pickup" in t or "Engine" in t for t in titles)
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_shipment_detail_endpoint(test_engine):
    """
    Tests retrieving full operational detail for a single shipment.
    """
    client, user, headers = await login_user(test_engine, "ops.lead@acme-mfg.com", "Password123!")
    try:
        # Get list of shipments to find ID of SHP-2026-9001
        res = await client.get("/api/v1/dashboard/tables/deliveries?search=SHP-2026-9001", headers=headers)
        shipment_id = res.json()["items"][0]["id"]

        detail_res = await client.get(f"/api/v1/dashboard/shipments/{shipment_id}", headers=headers)
        assert detail_res.status_code == 200
        detail = detail_res.json()

        assert detail["tracking_number"] == "SHP-2026-9001"
        assert detail["status"] == "DELIVERED"
        assert detail["origin_city"] == "Chicago"
        assert detail["destination_city"] == "Dallas"
        assert detail["pod_verified"] is True
        assert detail["pod_signatory_name"] == "John Reynolds"
        assert len(detail["events"]) >= 3
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_cross_tenant_isolation_on_dashboard(test_engine):
    """
    Ensures Tenant B cannot see Tenant A's metrics, shipments, or detail records.
    """
    client_b, user_b, headers_b, _ = await create_user_session(test_engine, "competitor")
    client_a, user_a, headers_a = await login_user(test_engine, "ops.lead@acme-mfg.com", "Password123!")

    try:
        # Tenant B dashboard should be 0
        res_b = await client_b.get("/api/v1/dashboard/metrics", headers=headers_b)
        assert res_b.status_code == 200
        assert res_b.json()["total_shipments"] == 0

        # Get Acme's shipment ID
        res_a = await client_a.get("/api/v1/dashboard/tables/deliveries?search=SHP-2026-9001", headers=headers_a)
        acme_shipment_id = res_a.json()["items"][0]["id"]

        # Tenant B attempts IDOR on Acme's shipment ID
        idor_res = await client_b.get(f"/api/v1/dashboard/shipments/{acme_shipment_id}", headers=headers_b)
        assert idor_res.status_code == 404
        assert "not found" in idor_res.json()["detail"].lower()
    finally:
        await client_b.aclose()
        await client_a.aclose()
