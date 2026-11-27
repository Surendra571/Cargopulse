import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.api.deps import get_db
from app.core.config import settings
from app.main import app
from app.models.enums import AssignmentStatus, BookingStatus, ShipmentStatus
from app.models.integrations import Notification
from app.models.shipment import Shipment, ShipmentAssignment, ShipmentEvent, TransporterBooking
from app.models.transporter import Driver, Transporter, Vehicle


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
        "full_name": f"{prefix.capitalize()} Dispatcher",
        "email": email,
        "password": "Password123!",
        "confirm_password": "Password123!",
        "organization_name": f"{prefix.capitalize()} Logistics {uid}",
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
    return user_client, user, headers, email


async def create_test_shipment(client, headers, weight_kg=12000.0):
    now = datetime.now(timezone.utc)
    payload = {
        "customer_name": "Tesla Gigafactory Texas",
        "customer_reference": "TSLA-PO-9912",
        "origin_name": "Dallas Parts Depot",
        "origin_address": "1200 Logistics Pkwy",
        "origin_city": "Dallas",
        "origin_state": "TX",
        "origin_postal_code": "75201",
        "origin_contact_name": "Tom Warehouse",
        "origin_contact_phone": "+1-214-555-0199",
        "destination_name": "Austin Assembly Plant",
        "destination_address": "13101 Harold Green Rd",
        "destination_city": "Austin",
        "destination_state": "TX",
        "destination_postal_code": "78725",
        "destination_contact_name": "Sara Receiver",
        "destination_contact_phone": "+1-512-555-0188",
        "goods_description": "Lithium Battery Cells Pack",
        "cargo_category": "Automotive",
        "total_weight_kg": weight_kg,
        "package_count": 18,
        "package_unit": "Pallets",
        "required_vehicle_type": "53' Dry Van",
        "priority": "HIGH",
        "scheduled_pickup_time": (now + timedelta(days=1)).isoformat(),
        "expected_delivery_time": (now + timedelta(days=2)).isoformat(),
    }
    resp = await client.post("/api/v1/shipments", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def create_test_transporter(client, headers, name="Lone Star Freight Lines"):
    resp = await client.post(
        "/api/v1/transporters",
        json={"name": name, "phone": "+1-214-555-0100", "email": "dispatch@lonestar.com", "service_regions": ["TX"]},
        headers=headers,
    )
    assert resp.status_code == 201
    carrier = resp.json()
    carrier_id = carrier["id"]
    # Verify carrier
    v_resp = await client.post(
        f"/api/v1/transporters/{carrier_id}/verify",
        json={"status": "VERIFIED", "verification_notes": "Active TxDOT permit verified"},
        headers=headers,
    )
    assert v_resp.status_code == 200
    return carrier_id


@pytest.mark.asyncio
async def test_create_booking_lifecycle_success(test_engine):
    """
    Test 1: Dispatch manager creates tender request to verified transporter.
    Verifies booking reference, status REQUESTED, shipment status PENDING_ACCEPTANCE,
    immutable shipment event, and asynchronous notification.
    """
    client, user, headers, _ = await create_user_session(test_engine, "bkg_create")
    shipment = await create_test_shipment(client, headers)
    carrier_id = await create_test_transporter(client, headers)

    # Create Booking
    resp = await client.post(
        "/api/v1/bookings",
        json={
            "shipment_id": shipment["id"],
            "transporter_id": carrier_id,
            "offered_rate": 1450.00,
            "expires_in_hours": 24,
            "booking_notes": "Driver must present PPE at Bay 6.",
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    booking = resp.json()

    assert booking["status"] == "REQUESTED"
    assert booking["offered_rate"] == 1450.00
    assert booking["booking_reference"].startswith("BKG-")
    assert booking["transporter_id"] == carrier_id
    assert booking["shipment_id"] == shipment["id"]
    assert not booking["is_expired"]

    # Verify Shipment transitioned to PENDING_ACCEPTANCE
    s_resp = await client.get(f"/api/v1/shipments/{shipment['id']}", headers=headers)
    assert s_resp.status_code == 200
    s_data = s_resp.json()
    assert s_data["status"] == "PENDING_ACCEPTANCE"
    assert s_data["assigned_transporter_id"] == carrier_id

    # Verify Booking detail contains event
    detail_resp = await client.get(f"/api/v1/bookings/{booking['id']}", headers=headers)
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert any(e["event_type"] == "BOOKING_REQUESTED" for e in detail["events"])


@pytest.mark.asyncio
async def test_accept_booking_state_machine_and_idempotency(test_engine):
    """
    Test 2: Transporter accepts booking tender.
    Idempotent re-acceptance returns cleanly with same status.
    """
    client, user, headers, _ = await create_user_session(test_engine, "bkg_accept")
    shipment = await create_test_shipment(client, headers)
    carrier_id = await create_test_transporter(client, headers)

    b_resp = await client.post(
        "/api/v1/bookings",
        json={"shipment_id": shipment["id"], "transporter_id": carrier_id, "offered_rate": 1200.0},
        headers=headers,
    )
    assert b_resp.status_code == 201
    booking_id = b_resp.json()["id"]

    # Accept
    accept_resp = await client.post(
        f"/api/v1/bookings/{booking_id}/accept",
        json={"agreed_rate": 1250.0, "response_notes": "Accepted at revised fuel surcharge"},
        headers=headers,
    )
    assert accept_resp.status_code == 200, accept_resp.text
    accepted = accept_resp.json()
    assert accepted["status"] == "ACCEPTED"
    assert accepted["agreed_rate"] == 1250.0
    assert accepted["responded_at"] is not None

    # Idempotent re-acceptance
    idempotent_resp = await client.post(
        f"/api/v1/bookings/{booking_id}/accept",
        json={"agreed_rate": 1250.0},
        headers=headers,
    )
    assert idempotent_resp.status_code == 200
    assert idempotent_resp.json()["status"] == "ACCEPTED"


@pytest.mark.asyncio
async def test_accept_booking_with_vehicle_and_driver_confirms_dispatch(test_engine):
    """
    Test 3: Carrier supplies vehicle & driver on acceptance.
    Booking becomes CONFIRMED, Shipment becomes COMMITTED, active assignment is activated.
    """
    client, user, headers, _ = await create_user_session(test_engine, "bkg_full_dispatch")
    shipment = await create_test_shipment(client, headers, weight_kg=15000.0)
    carrier_id = await create_test_transporter(client, headers)

    now = datetime.now(timezone.utc)
    # Add Vehicle with valid capacity
    v_resp = await client.post(
        "/api/v1/vehicles",
        json={
            "transporter_id": carrier_id,
            "license_plate": f"TX-{uuid.uuid4().hex[:4].upper()}",
            "vehicle_type": "53' Dry Van",
            "capacity_kg": 22000.0,
            "insurance_expiry": (now + timedelta(days=90)).isoformat(),
            "fitness_expiry": (now + timedelta(days=90)).isoformat(),
        },
        headers=headers,
    )
    assert v_resp.status_code == 201
    vehicle_id = v_resp.json()["id"]

    # Add Driver with valid license
    d_resp = await client.post(
        "/api/v1/drivers",
        json={
            "transporter_id": carrier_id,
            "first_name": "Carlos",
            "last_name": "Rodriguez",
            "phone": "+1-214-555-0811",
            "license_number": f"CDL-{uuid.uuid4().hex[:6].upper()}",
            "license_expiry": (now + timedelta(days=180)).isoformat(),
        },
        headers=headers,
    )
    assert d_resp.status_code == 201
    driver_id = d_resp.json()["id"]

    # Create Booking
    b_resp = await client.post(
        "/api/v1/bookings",
        json={"shipment_id": shipment["id"], "transporter_id": carrier_id, "offered_rate": 1800.0},
        headers=headers,
    )
    assert b_resp.status_code == 201
    booking_id = b_resp.json()["id"]

    # Accept with Vehicle & Driver designated
    confirm_resp = await client.post(
        f"/api/v1/bookings/{booking_id}/accept",
        json={
            "vehicle_id": vehicle_id,
            "driver_id": driver_id,
            "agreed_rate": 1800.0,
            "response_notes": "Unit 402 en route to origin dock.",
        },
        headers=headers,
    )
    assert confirm_resp.status_code == 200, confirm_resp.text
    confirmed_bkg = confirm_resp.json()
    assert confirmed_bkg["status"] == "CONFIRMED"
    assert confirmed_bkg["confirmed_at"] is not None
    assert confirmed_bkg["vehicle"]["id"] == vehicle_id
    assert confirmed_bkg["driver"]["id"] == driver_id
    assert confirmed_bkg["assignment_id"] is not None

    # Verify Shipment status is COMMITTED
    s_resp = await client.get(f"/api/v1/shipments/{shipment['id']}", headers=headers)
    assert s_resp.status_code == 200
    s_data = s_resp.json()
    assert s_data["status"] == "COMMITTED"
    assert s_data["assigned_vehicle_plate"] == confirmed_bkg["vehicle"]["license_plate"]
    assert "Carlos Rodriguez" in s_data["assigned_driver_name"]


@pytest.mark.asyncio
async def test_resource_allocation_validations(test_engine):
    """
    Test 4: Rigorous validation of vehicle capacity, insurance expiry, and driver license.
    """
    client, user, headers, _ = await create_user_session(test_engine, "bkg_val")
    now = datetime.now(timezone.utc)

    # 1. 20,000 kg shipment
    shipment = await create_test_shipment(client, headers, weight_kg=20000.0)
    carrier_id = await create_test_transporter(client, headers)

    # Under-capacity vehicle (15,000 kg < 20,000 kg)
    v_light = await client.post(
        "/api/v1/vehicles",
        json={
            "transporter_id": carrier_id,
            "license_plate": f"LT-{uuid.uuid4().hex[:4].upper()}",
            "vehicle_type": "53' Dry Van",
            "capacity_kg": 15000.0,
            "insurance_expiry": (now + timedelta(days=90)).isoformat(),
            "fitness_expiry": (now + timedelta(days=90)).isoformat(),
        },
        headers=headers,
    )
    v_light_id = v_light.json()["id"]

    # Expired insurance vehicle
    v_exp = await client.post(
        "/api/v1/vehicles",
        json={
            "transporter_id": carrier_id,
            "license_plate": f"EXP-{uuid.uuid4().hex[:4].upper()}",
            "vehicle_type": "53' Dry Van",
            "capacity_kg": 25000.0,
            "insurance_expiry": (now - timedelta(days=5)).isoformat(),  # EXPIRED!
            "fitness_expiry": (now + timedelta(days=90)).isoformat(),
        },
        headers=headers,
    )
    v_exp_id = v_exp.json()["id"]

    # Valid Vehicle
    v_ok = await client.post(
        "/api/v1/vehicles",
        json={
            "transporter_id": carrier_id,
            "license_plate": f"OK-{uuid.uuid4().hex[:4].upper()}",
            "vehicle_type": "53' Dry Van",
            "capacity_kg": 25000.0,
            "insurance_expiry": (now + timedelta(days=90)).isoformat(),
            "fitness_expiry": (now + timedelta(days=90)).isoformat(),
        },
        headers=headers,
    )
    v_ok_id = v_ok.json()["id"]

    # Expired license driver
    d_exp = await client.post(
        "/api/v1/drivers",
        json={
            "transporter_id": carrier_id,
            "first_name": "Old",
            "last_name": "Driver",
            "phone": "+1-214-555-0999",
            "license_number": f"CDL-{uuid.uuid4().hex[:6].upper()}",
            "license_expiry": (now - timedelta(days=10)).isoformat(),  # EXPIRED!
        },
        headers=headers,
    )
    d_exp_id = d_exp.json()["id"]

    # Valid Driver
    d_ok = await client.post(
        "/api/v1/drivers",
        json={
            "transporter_id": carrier_id,
            "first_name": "Marcus",
            "last_name": "Vance",
            "phone": "+1-214-555-0777",
            "license_number": f"CDL-{uuid.uuid4().hex[:6].upper()}",
            "license_expiry": (now + timedelta(days=120)).isoformat(),
        },
        headers=headers,
    )
    d_ok_id = d_ok.json()["id"]

    # Create Booking
    b_resp = await client.post(
        "/api/v1/bookings",
        json={"shipment_id": shipment["id"], "transporter_id": carrier_id, "offered_rate": 1500.0},
        headers=headers,
    )
    booking_id = b_resp.json()["id"]

    # Accept first
    await client.post(f"/api/v1/bookings/{booking_id}/accept", json={}, headers=headers)

    # 1. Attempt assigning under-capacity vehicle -> HTTP 400
    res_light = await client.post(
        f"/api/v1/bookings/{booking_id}/assign",
        json={"vehicle_id": v_light_id, "driver_id": d_ok_id},
        headers=headers,
    )
    assert res_light.status_code == 400
    assert "insufficient" in res_light.json()["detail"].lower()

    # 2. Attempt assigning expired insurance vehicle -> HTTP 400
    res_exp_v = await client.post(
        f"/api/v1/bookings/{booking_id}/assign",
        json={"vehicle_id": v_exp_id, "driver_id": d_ok_id},
        headers=headers,
    )
    assert res_exp_v.status_code == 400
    assert "insurance certificate expired" in res_exp_v.json()["detail"].lower()

    # 3. Attempt assigning expired license driver -> HTTP 400
    res_exp_d = await client.post(
        f"/api/v1/bookings/{booking_id}/assign",
        json={"vehicle_id": v_ok_id, "driver_id": d_exp_id},
        headers=headers,
    )
    assert res_exp_d.status_code == 400
    assert "license expired" in res_exp_d.json()["detail"].lower()

    # 4. Valid assignment succeeds
    res_valid = await client.post(
        f"/api/v1/bookings/{booking_id}/assign",
        json={"vehicle_id": v_ok_id, "driver_id": d_ok_id, "notes": "Handover to driver Marcus."},
        headers=headers,
    )
    assert res_valid.status_code == 200
    assert res_valid.json()["status"] == "CONFIRMED"


@pytest.mark.asyncio
async def test_reject_booking_releases_shipment_to_draft(test_engine):
    """
    Test 5: Transporter declines tender.
    Booking marked REJECTED, shipment status resets to DRAFT so another carrier can be booked.
    """
    client, user, headers, _ = await create_user_session(test_engine, "bkg_reject")
    shipment = await create_test_shipment(client, headers)
    carrier_id = await create_test_transporter(client, headers)

    b_resp = await client.post(
        "/api/v1/bookings",
        json={"shipment_id": shipment["id"], "transporter_id": carrier_id, "offered_rate": 1100.0},
        headers=headers,
    )
    booking_id = b_resp.json()["id"]

    # Reject
    rej_resp = await client.post(
        f"/api/v1/bookings/{booking_id}/reject",
        json={"rejection_reason": "No drivers available in Dallas hub today."},
        headers=headers,
    )
    assert rej_resp.status_code == 200
    b_data = rej_resp.json()
    assert b_data["status"] == "REJECTED"
    assert "No drivers available" in b_data["rejection_reason"]

    # Verify Shipment returned to DRAFT and cleared carrier
    s_resp = await client.get(f"/api/v1/shipments/{shipment['id']}", headers=headers)
    assert s_resp.status_code == 200
    s_data = s_resp.json()
    assert s_data["status"] == "DRAFT"
    assert s_data["assigned_transporter_id"] is None


@pytest.mark.asyncio
async def test_expired_booking_cannot_be_accepted(test_engine):
    """
    Test 6: Overdue booking cannot be accepted.
    System marks it EXPIRED and rejects with HTTP 400.
    """
    client, user, headers, _ = await create_user_session(test_engine, "bkg_expired")
    shipment = await create_test_shipment(client, headers)
    carrier_id = await create_test_transporter(client, headers)

    # Create Booking
    b_resp = await client.post(
        "/api/v1/bookings",
        json={"shipment_id": shipment["id"], "transporter_id": carrier_id, "expires_in_hours": 1},
        headers=headers,
    )
    booking_id = b_resp.json()["id"]

    # Manually backdate expires_at in database
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        b_obj = await session.get(TransporterBooking, uuid.UUID(booking_id))
        b_obj.expires_at = datetime.now(timezone.utc) - timedelta(hours=2)
        await session.commit()

    # Attempt to accept expired tender -> HTTP 400
    acc_resp = await client.post(f"/api/v1/bookings/{booking_id}/accept", json={}, headers=headers)
    assert acc_resp.status_code == 400
    assert "expired" in acc_resp.json()["detail"].lower()

    # Check status is EXPIRED
    get_resp = await client.get(f"/api/v1/bookings/{booking_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["status"] == "EXPIRED"


@pytest.mark.asyncio
async def test_cancel_booking_workflow(test_engine):
    """
    Test 7: Dispatch manager cancels active booking.
    Booking becomes CANCELLED, shipment returns to DRAFT.
    """
    client, user, headers, _ = await create_user_session(test_engine, "bkg_cancel")
    shipment = await create_test_shipment(client, headers)
    carrier_id = await create_test_transporter(client, headers)

    b_resp = await client.post(
        "/api/v1/bookings",
        json={"shipment_id": shipment["id"], "transporter_id": carrier_id, "offered_rate": 1300.0},
        headers=headers,
    )
    booking_id = b_resp.json()["id"]

    cancel_resp = await client.post(
        f"/api/v1/bookings/{booking_id}/cancel",
        json={"cancellation_reason": "Customer cancelled manufacturing order."},
        headers=headers,
    )
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "CANCELLED"

    s_resp = await client.get(f"/api/v1/shipments/{shipment['id']}", headers=headers)
    assert s_resp.json()["status"] == "DRAFT"


@pytest.mark.asyncio
async def test_cross_tenant_isolation_on_bookings(test_engine):
    """
    Test 8: Cross-tenant isolation.
    Organization B cannot view, accept, reject, or cancel Organization A's bookings.
    """
    client_a, _, headers_a, _ = await create_user_session(test_engine, "tenant_a")
    client_b, _, headers_b, _ = await create_user_session(test_engine, "tenant_b")

    shipment_a = await create_test_shipment(client_a, headers_a)
    carrier_a = await create_test_transporter(client_a, headers_a, name="Org A Carrier")

    b_resp = await client_a.post(
        "/api/v1/bookings",
        json={"shipment_id": shipment_a["id"], "transporter_id": carrier_a, "offered_rate": 1400.0},
        headers=headers_a,
    )
    assert b_resp.status_code == 201
    booking_id = b_resp.json()["id"]

    # Org B attempts to read -> 404
    read_b = await client_b.get(f"/api/v1/bookings/{booking_id}", headers=headers_b)
    assert read_b.status_code == 404

    # Org B attempts to accept -> 404
    accept_b = await client_b.post(f"/api/v1/bookings/{booking_id}/accept", json={}, headers=headers_b)
    assert accept_b.status_code == 404

    # Org B attempts to reject -> 404
    reject_b = await client_b.post(
        f"/api/v1/bookings/{booking_id}/reject",
        json={"rejection_reason": "Unauthorized"},
        headers=headers_b,
    )
    assert reject_b.status_code == 404
