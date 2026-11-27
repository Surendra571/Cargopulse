import uuid
from datetime import datetime, timedelta, timezone
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.api.deps import get_db
from app.core.config import settings
from app.main import app
from app.models.transporter import Transporter, Vehicle
from app.services.transporter_service import TransporterService


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


@pytest.mark.asyncio
async def test_create_and_list_transporters(test_engine):
    """Test creating a transporter, auto code generation, and listing."""
    client, user, headers, _ = await create_user_session(test_engine, "carrier_create")

    payload = {
        "name": "Midwest Express Freight LLC",
        "contact_person": "Robert Sterling",
        "phone": "+1-312-555-0199",
        "email": "dispatch@midwestexpress.com",
        "gstin": "27AAAPL1234A1Z5",
        "service_regions": ["Midwest", "Great Lakes", "Chicago Metro"],
        "operating_routes": ["Chicago -> Detroit", "Detroit -> Cleveland"],
        "vehicle_categories": ["53' Dry Van", "Flatbed 48'"],
        "max_cargo_capacity_kg": 25000.0,
    }

    create_resp = await client.post("/api/v1/transporters", json=payload, headers=headers)
    assert create_resp.status_code == 201, create_resp.text
    carrier = create_resp.json()

    assert carrier["id"] is not None
    assert carrier["name"] == "Midwest Express Freight LLC"
    assert carrier["verification_status"] == "REGISTERED"
    assert carrier["account_status"] == "ACTIVE"
    assert len(carrier["service_regions"]) == 3

    # List
    list_resp = await client.get("/api/v1/transporters", headers=headers)
    assert list_resp.status_code == 200
    res = list_resp.json()
    assert res["total"] >= 1
    assert any(c["id"] == carrier["id"] for c in res["items"])


@pytest.mark.asyncio
async def test_verify_and_suspend_transporter_lifecycle(test_engine):
    """Test verification transitions (DOCUMENTS_SUBMITTED -> VERIFIED -> SUSPENDED)."""
    client, user, headers, _ = await create_user_session(test_engine, "carrier_verify")

    create_resp = await client.post(
        "/api/v1/transporters",
        json={
            "name": "Titan Heavy Haul Inc",
            "phone": "+1-414-555-0188",
            "service_regions": ["Upper Midwest"],
        },
        headers=headers,
    )
    assert create_resp.status_code == 201
    carrier_id = create_resp.json()["id"]

    # 1. Upload document (auto-promotes to DOCUMENTS_SUBMITTED)
    doc_payload = {
        "doc_type": "MOTOR_CARRIER_PERMIT",
        "document_number": "MCP-2026-9901",
        "file_url": "https://storage.cargopulse.internal/docs/mcp-titan.pdf",
        "expiry_date": (datetime.now(timezone.utc) + timedelta(days=365)).isoformat(),
    }
    doc_resp = await client.post(f"/api/v1/transporters/{carrier_id}/documents", json=doc_payload, headers=headers)
    assert doc_resp.status_code == 200
    assert doc_resp.json()["verification_status"] == "DOCUMENTS_SUBMITTED"

    # 2. Verify carrier
    verify_resp = await client.post(
        f"/api/v1/transporters/{carrier_id}/verify",
        json={"status": "VERIFIED", "verification_notes": "Audit completed. Safety rating satisfactory."},
        headers=headers,
    )
    assert verify_resp.status_code == 200
    assert verify_resp.json()["verification_status"] == "VERIFIED"
    assert verify_resp.json()["verified_at"] is not None

    # 3. Suspend carrier
    suspend_resp = await client.post(
        f"/api/v1/transporters/{carrier_id}/suspend?reason=Failed+safety+inspection",
        headers=headers,
    )
    assert suspend_resp.status_code == 200
    assert suspend_resp.json()["verification_status"] == "SUSPENDED"
    assert suspend_resp.json()["is_active"] is False


@pytest.mark.asyncio
async def test_transporter_booking_eligibility_business_rule(test_engine):
    """Business Rule: Unverified or suspended transporters cannot receive active bookings."""
    # Test service helper directly
    transporter = Transporter(
        id=uuid.uuid4(),
        name="Unverified Carrier",
        is_active=True,
        compliance_details={"verification_status": "REGISTERED"},
    )
    with pytest.raises(Exception) as excinfo:
        TransporterService.verify_transporter_eligible_for_booking(transporter)
    assert "Only verified transporters can receive active bookings" in str(excinfo.value.detail)

    # Suspended carrier
    transporter_susp = Transporter(
        id=uuid.uuid4(),
        name="Suspended Carrier",
        is_active=False,
        compliance_details={"verification_status": "SUSPENDED"},
    )
    with pytest.raises(Exception) as excinfo2:
        TransporterService.verify_transporter_eligible_for_booking(transporter_susp)
    assert "is suspended" in str(excinfo2.value.detail)


@pytest.mark.asyncio
async def test_create_vehicle_and_prevent_duplicate_plate(test_engine):
    """Test vehicle creation, capacity checks, and unique license plate enforcement."""
    client, user, headers, _ = await create_user_session(test_engine, "vehicle_crud")

    # Create carrier first
    c_resp = await client.post("/api/v1/transporters", json={"name": "Swift Logistics", "phone": "+1-555-0101"}, headers=headers)
    carrier_id = c_resp.json()["id"]

    v_payload = {
        "transporter_id": carrier_id,
        "license_plate": "IL-TRK-8812",
        "vehicle_type": "53' Dry Van",
        "capacity_kg": 20000.0,
        "volume_cbm": 90.0,
        "rc_number": "RC-IL-9901",
        "insurance_expiry": (datetime.now(timezone.utc) + timedelta(days=180)).isoformat(),
        "fitness_expiry": (datetime.now(timezone.utc) + timedelta(days=180)).isoformat(),
        "telematics_device_id": "GPS-SWIFT-01",
        "is_available": True,
    }

    resp = await client.post("/api/v1/vehicles", json=v_payload, headers=headers)
    assert resp.status_code == 201
    veh = resp.json()
    assert veh["license_plate"] == "IL-TRK-8812"
    assert veh["status"] == "ACTIVE"
    assert veh["has_expired_documents"] is False

    # Attempt duplicate license plate registration -> 409 Conflict
    dup_resp = await client.post("/api/v1/vehicles", json=v_payload, headers=headers)
    assert dup_resp.status_code == 409


@pytest.mark.asyncio
async def test_vehicle_capacity_and_document_expiration_rules(test_engine):
    """Test vehicle capacity requirement and expired document eligibility restrictions."""
    now = datetime.now(timezone.utc)

    # 1. Insufficient capacity
    low_cap_vehicle = Vehicle(
        id=uuid.uuid4(),
        license_plate="PLATE-01",
        capacity_kg=5000.0,
        insurance_expiry=now + timedelta(days=30),
        fitness_expiry=now + timedelta(days=30),
    )
    with pytest.raises(Exception) as exc1:
        TransporterService.verify_vehicle_capacity_and_documents(low_cap_vehicle, required_weight_kg=8000.0)
    assert "insufficient for shipment weight" in str(exc1.value.detail)

    # 2. Expired insurance
    expired_ins_vehicle = Vehicle(
        id=uuid.uuid4(),
        license_plate="PLATE-02",
        capacity_kg=25000.0,
        insurance_expiry=now - timedelta(days=5),  # expired!
        fitness_expiry=now + timedelta(days=30),
    )
    with pytest.raises(Exception) as exc2:
        TransporterService.verify_vehicle_capacity_and_documents(expired_ins_vehicle, required_weight_kg=10000.0)
    assert "Insurance policy has expired" in str(exc2.value.detail)


@pytest.mark.asyncio
async def test_create_driver_and_masked_license_protection(test_engine):
    """Test driver creation and privacy masking of license numbers."""
    client, user, headers, _ = await create_user_session(test_engine, "driver_crud")

    c_resp = await client.post("/api/v1/transporters", json={"name": "Eagle Transport", "phone": "+1-555-0102"}, headers=headers)
    carrier_id = c_resp.json()["id"]

    d_payload = {
        "transporter_id": carrier_id,
        "first_name": "Marcus",
        "last_name": "Vance",
        "phone": "+1-312-555-0455",
        "license_number": "CDL-IL-987654321",
        "license_expiry": (datetime.now(timezone.utc) + timedelta(days=300)).isoformat(),
        "is_available": True,
    }

    resp = await client.post("/api/v1/drivers", json=d_payload, headers=headers)
    assert resp.status_code == 201
    driver = resp.json()
    assert driver["full_name"] == "Marcus Vance"
    assert driver["license_number_masked"].endswith("4321")
    assert driver["status"] == "ACTIVE"

    # Attempt duplicate driver phone -> 409 Conflict
    dup_resp = await client.post("/api/v1/drivers", json=d_payload, headers=headers)
    assert dup_resp.status_code == 409


@pytest.mark.asyncio
async def test_driver_vehicle_assignment_and_license_expiry_rule(test_engine):
    """Test assigning driver to vehicle and blocking assignment if license is expired."""
    client, user, headers, _ = await create_user_session(test_engine, "driver_assign")

    c_resp = await client.post("/api/v1/transporters", json={"name": "Pioneer Freight", "phone": "+1-555-0103"}, headers=headers)
    carrier_id = c_resp.json()["id"]

    # Register vehicle
    v_resp = await client.post(
        "/api/v1/vehicles",
        json={
            "transporter_id": carrier_id,
            "license_plate": "MI-PION-01",
            "vehicle_type": "Box Truck 26'",
            "capacity_kg": 10000.0,
        },
        headers=headers,
    )
    vehicle_id = v_resp.json()["id"]

    # Register driver with EXPIRED license
    d_resp = await client.post(
        "/api/v1/drivers",
        json={
            "transporter_id": carrier_id,
            "first_name": "Dave",
            "last_name": "Miller",
            "phone": "+1-313-555-0771",
            "license_number": "DL-MI-112233",
            "license_expiry": (datetime.now(timezone.utc) - timedelta(days=10)).isoformat(),  # expired!
        },
        headers=headers,
    )
    driver_id = d_resp.json()["id"]
    assert d_resp.json()["status"] == "EXPIRED_LICENSE"

    # Attempt to assign driver with expired license to vehicle -> 400 Bad Request
    assign_resp = await client.post(
        f"/api/v1/drivers/{driver_id}/assign-vehicle",
        json={"vehicle_id": vehicle_id},
        headers=headers,
    )
    assert assign_resp.status_code == 400
    assert "commercial license has expired" in assign_resp.json()["detail"]


@pytest.mark.asyncio
async def test_cross_tenant_isolation_idor_protection(test_engine):
    """Verify Tenant B cannot view or modify Tenant A's transporter records."""
    client_a, _, headers_a, _ = await create_user_session(test_engine, "tenant_a_trp")
    client_b, _, headers_b, _ = await create_user_session(test_engine, "tenant_b_trp")

    # Tenant A creates carrier
    c_resp = await client_a.post("/api/v1/transporters", json={"name": "Org A Dedicated Carriers", "phone": "+1-555-0191"}, headers=headers_a)
    carrier_id = c_resp.json()["id"]

    # Tenant B tries to get Tenant A's carrier -> 404
    resp_get = await client_b.get(f"/api/v1/transporters/{carrier_id}", headers=headers_b)
    assert resp_get.status_code == 404

    # Tenant B tries to update Tenant A's carrier -> 404
    resp_put = await client_b.put(f"/api/v1/transporters/{carrier_id}", json={"name": "Hacked Carrier"}, headers=headers_b)
    assert resp_put.status_code == 404
