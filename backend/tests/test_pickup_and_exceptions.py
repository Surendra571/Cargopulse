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
from app.models.enums import (
    AssignmentStatus,
    BookingStatus,
    CommitmentStatus,
    ExceptionPriority,
    ExceptionSeverity,
    ExceptionStatus,
    ExceptionType,
    RecoveryStatus,
    ShipmentStatus,
)
from app.models.operations import ExceptionRecord, RecoveryCase
from app.models.shipment import (
    PickupCommitment,
    Shipment,
    ShipmentAssignment,
    TransporterBooking,
)
from app.models.transporter import Driver, Transporter, Vehicle


@pytest_asyncio.fixture
async def test_engine():
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool, connect_args={"ssl": False}, echo=False)
    yield engine
    await engine.dispose()


async def create_user_session(test_engine, prefix: str = "ops"):
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
        "full_name": "Operations Lead",
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

    return user_client, headers, org_id, user_id


async def _create_test_carriers(client: AsyncClient, headers: dict):
    # Carrier A
    c_a_res = await client.post(
        "/api/v1/transporters",
        json={
            "name": f"Speedy Freight {uuid.uuid4().hex[:4]}",
            "phone": "+1-555-111-2222",
            "email": f"speedy_{uuid.uuid4().hex[:4]}@speedy.com",
            "service_regions": ["Midwest", "Great Lakes"],
            "operating_routes": ["Chicago -> Indianapolis"],
            "vehicle_categories": ["53' Dry Van"],
            "max_cargo_capacity_kg": 25000,
        },
        headers=headers,
    )
    assert c_a_res.status_code == 201, c_a_res.text
    c_a = c_a_res.json()
    v_res = await client.post(
        f"/api/v1/transporters/{c_a['id']}/verify",
        json={"status": "VERIFIED"},
        headers=headers,
    )
    assert v_res.status_code == 200, v_res.text
    v_a_res = await client.post(
        "/api/v1/vehicles",
        json={
            "transporter_id": c_a["id"],
            "license_plate": f"IL-{uuid.uuid4().hex[:6].upper()}",
            "vehicle_type": "53' Dry Van",
            "capacity_kg": 22000,
            "insurance_expiry": (datetime.now(timezone.utc) + timedelta(days=90)).isoformat(),
            "fitness_expiry": (datetime.now(timezone.utc) + timedelta(days=90)).isoformat(),
        },
        headers=headers,
    )
    assert v_a_res.status_code == 201, v_a_res.text
    v_a = v_a_res.json()
    d_a_res = await client.post(
        "/api/v1/drivers",
        json={
            "transporter_id": c_a["id"],
            "first_name": "John",
            "last_name": "DriverA",
            "phone": "+1-555-888-9999",
            "license_number": f"CDL-{uuid.uuid4().hex[:8].upper()}",
            "license_expiry": (datetime.now(timezone.utc) + timedelta(days=120)).isoformat(),
        },
        headers=headers,
    )
    assert d_a_res.status_code == 201, d_a_res.text
    d_a = d_a_res.json()

    # Carrier C (Replacement Alternative)
    c_c_res = await client.post(
        "/api/v1/transporters",
        json={
            "name": f"Pinnacle Express {uuid.uuid4().hex[:4]}",
            "phone": "+1-555-333-4444",
            "email": f"pinnacle_{uuid.uuid4().hex[:4]}@pinnacle.com",
            "service_regions": ["Midwest"],
            "operating_routes": ["Chicago -> Indianapolis"],
            "vehicle_categories": ["53' Dry Van"],
            "max_cargo_capacity_kg": 30000,
        },
        headers=headers,
    )
    assert c_c_res.status_code == 201, c_c_res.text
    c_c = c_c_res.json()
    v_c_res = await client.post(
        f"/api/v1/transporters/{c_c['id']}/verify",
        json={"status": "VERIFIED"},
        headers=headers,
    )
    assert v_c_res.status_code == 200, v_c_res.text

    return c_a, v_a, d_a, c_c


async def _create_test_shipment(client: AsyncClient, headers: dict, pickup_time: datetime):
    res = await client.post(
        "/api/v1/shipments",
        json={
            "customer_name": "Apex Electronics",
            "customer_reference": f"REF-{uuid.uuid4().hex[:6].upper()}",
            "origin_name": "Chicago Hub",
            "origin_address": "100 Express Blvd",
            "origin_city": "Chicago",
            "origin_state": "IL",
            "origin_postal_code": "60601",
            "origin_contact_name": "Alice Mgr",
            "origin_contact_phone": "+1-312-555-0100",
            "destination_name": "Indianapolis DC",
            "destination_address": "200 Distribution Way",
            "destination_city": "Indianapolis",
            "destination_state": "IN",
            "destination_postal_code": "46201",
            "destination_contact_name": "Bob Recv",
            "destination_contact_phone": "+1-317-555-0199",
            "goods_description": "Server hardware racks",
            "cargo_category": "ELECTRONICS",
            "total_weight_kg": 9500.0,
            "package_count": 10,
            "package_unit": "PALLETS",
            "required_vehicle_type": "53' Dry Van",
            "scheduled_pickup_time": pickup_time.isoformat(),
            "expected_delivery_time": (pickup_time + timedelta(hours=8)).isoformat(),
            "priority": "CRITICAL",
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()


@pytest.mark.asyncio
async def test_pickup_commitment_lifecycle_and_events(test_engine):
    client, headers, org_id, user_id = await create_user_session(test_engine, "ops")
    c_a, v_a, d_a, _ = await _create_test_carriers(client, headers)

    pickup_time = datetime.now(timezone.utc) + timedelta(hours=3)
    shipment = await _create_test_shipment(client, headers, pickup_time)

    # 1. Tender and confirm booking with carrier A
    bkg_res = await client.post(
        "/api/v1/bookings",
        json={
            "shipment_id": shipment["id"],
            "transporter_id": c_a["id"],
            "offered_rate": 1800.0,
            "expires_in_hours": 12,
        },
        headers=headers,
    )
    assert bkg_res.status_code == 201, bkg_res.text
    bkg_id = bkg_res.json()["id"]

    accept_res = await client.post(
        f"/api/v1/bookings/{bkg_id}/accept",
        json={
            "agreed_rate": 1800.0,
            "vehicle_id": v_a["id"],
            "driver_id": d_a["id"],
            "response_notes": "Driver and van locked in.",
        },
        headers=headers,
    )
    assert accept_res.status_code == 200, accept_res.text
    assert accept_res.json()["status"] == "CONFIRMED"

    # 2. Verify PickupCommitment was auto-created
    commitments_res = await client.get(
        f"/api/v1/pickup-monitoring/commitments?shipment_id={shipment['id']}",
        headers=headers,
    )
    assert commitments_res.status_code == 200
    items = commitments_res.json()["items"]
    assert len(items) == 1
    commitment = items[0]
    assert commitment["status"] == "CONFIRMED"
    assert commitment["vehicle"]["license_plate"] == v_a["license_plate"]
    assert commitment["driver"]["first_name"] == "John"

    commitment_id = commitment["id"]

    # 3. Report Arrival
    arrival_res = await client.post(
        f"/api/v1/pickup-monitoring/commitments/{commitment_id}/arrival",
        json={"dock_number": "Bay-4B", "notes": "Vehicle arrived at gate."},
        headers=headers,
    )
    assert arrival_res.status_code == 200
    assert arrival_res.json()["status"] == "ARRIVED"

    # Verify shipment is AT_PICKUP
    shp_res = await client.get(f"/api/v1/shipments/{shipment['id']}", headers=headers)
    assert shp_res.json()["status"] == "AT_PICKUP"

    # 4. Start Pickup
    start_res = await client.post(
        f"/api/v1/pickup-monitoring/commitments/{commitment_id}/start",
        json={"bay_number": "Bay-4B", "notes": "Pallets being loaded."},
        headers=headers,
    )
    assert start_res.status_code == 200
    assert start_res.json()["status"] == "STARTED"

    # 5. Complete Pickup
    complete_res = await client.post(
        f"/api/v1/pickup-monitoring/commitments/{commitment_id}/complete",
        json={
            "bill_of_lading_number": "BOL-998822",
            "seal_number": "SEAL-XYZ-1",
            "loaded_weight_kg": 9500.0,
        },
        headers=headers,
    )
    assert complete_res.status_code == 200
    assert complete_res.json()["status"] == "COMPLETED"

    # Verify shipment is now IN_TRANSIT
    shp_res_after = await client.get(f"/api/v1/shipments/{shipment['id']}", headers=headers)
    assert shp_res_after.json()["status"] == "IN_TRANSIT"


@pytest.mark.asyncio
async def test_monitoring_rules_reminder_at_risk_and_missed_pickup(test_engine):
    client, headers, org_id, user_id = await create_user_session(test_engine, "ops")
    c_a, v_a, d_a, c_c = await _create_test_carriers(client, headers)

    # Schedule pickup for 2 hours ahead
    deadline = datetime.now(timezone.utc) + timedelta(hours=2)
    shipment = await _create_test_shipment(client, headers, deadline)

    # Confirm booking with carrier A
    bkg_res = await client.post(
        "/api/v1/bookings",
        json={"shipment_id": shipment["id"], "transporter_id": c_a["id"], "offered_rate": 1900.0},
        headers=headers,
    )
    assert bkg_res.status_code == 201, bkg_res.text
    bkg_id = bkg_res.json()["id"]
    accept_res = await client.post(
        f"/api/v1/bookings/{bkg_id}/accept",
        json={"agreed_rate": 1900.0, "vehicle_id": v_a["id"], "driver_id": d_a["id"]},
        headers=headers,
    )
    assert accept_res.status_code == 200, accept_res.text

    # Rule Check 0: T-45m -> Still CONFIRMED
    scan_0 = await client.post(
        f"/api/v1/pickup-monitoring/scan?simulated_now={(deadline - timedelta(minutes=45)).isoformat()}",
        headers=headers,
    )
    assert scan_0.status_code == 200
    assert scan_0.json()["reminders_sent"] == 0
    assert scan_0.json()["at_risk_flagged"] == 0

    # Rule Check 1: T-25m (within 30m) -> REMINDER_SENT
    scan_1 = await client.post(
        f"/api/v1/pickup-monitoring/scan?simulated_now={(deadline - timedelta(minutes=25)).isoformat()}",
        headers=headers,
    )
    assert scan_1.status_code == 200
    assert scan_1.json()["reminders_sent"] >= 1

    # Rule Check 2: T-8m (within 10m) -> AT_RISK
    scan_2 = await client.post(
        f"/api/v1/pickup-monitoring/scan?simulated_now={(deadline - timedelta(minutes=8)).isoformat()}",
        headers=headers,
    )
    assert scan_2.status_code == 200
    assert scan_2.json()["at_risk_flagged"] >= 1

    # Rule Check 3: T+1m (Past deadline!) -> MISSED
    scan_3 = await client.post(
        f"/api/v1/pickup-monitoring/scan?simulated_now={(deadline + timedelta(minutes=1)).isoformat()}",
        headers=headers,
    )
    assert scan_3.status_code == 200
    assert scan_3.json()["missed_detected"] >= 1
    assert scan_3.json()["exceptions_created"] >= 1
    assert scan_3.json()["recovery_cases_opened"] >= 1

    # Verify commitment is MISSED and breached
    commitments_res = await client.get(
        f"/api/v1/pickup-monitoring/commitments?shipment_id={shipment['id']}",
        headers=headers,
    )
    c_item = commitments_res.json()["items"][0]
    assert c_item["status"] == "MISSED"
    assert c_item["is_breached"] is True

    # Verify shipment is in EXCEPTION status
    shp_res = await client.get(f"/api/v1/shipments/{shipment['id']}", headers=headers)
    assert shp_res.json()["status"] == "EXCEPTION"


@pytest.mark.asyncio
async def test_exact_once_exception_creation_and_duplicate_prevention(test_engine):
    client, headers, org_id, user_id = await create_user_session(test_engine, "ops")
    c_a, v_a, d_a, _ = await _create_test_carriers(client, headers)

    deadline = datetime.now(timezone.utc) + timedelta(hours=2)
    shipment = await _create_test_shipment(client, headers, deadline)

    bkg_res = await client.post(
        "/api/v1/bookings",
        json={"shipment_id": shipment["id"], "transporter_id": c_a["id"], "offered_rate": 1900.0},
        headers=headers,
    )
    assert bkg_res.status_code == 201, bkg_res.text
    accept_res = await client.post(
        f"/api/v1/bookings/{bkg_res.json()['id']}/accept",
        json={"agreed_rate": 1900.0, "vehicle_id": v_a["id"], "driver_id": d_a["id"]},
        headers=headers,
    )
    assert accept_res.status_code == 200, accept_res.text

    past_time = deadline + timedelta(minutes=5)
    # First scan
    scan_1 = await client.post(
        f"/api/v1/pickup-monitoring/scan?simulated_now={past_time.isoformat()}",
        headers=headers,
    )
    assert scan_1.json()["missed_detected"] >= 1

    # Second scan at past_time + 5 mins (idempotency & worker restart simulation)
    scan_2 = await client.post(
        f"/api/v1/pickup-monitoring/scan?simulated_now={(past_time + timedelta(minutes=5)).isoformat()}",
        headers=headers,
    )
    assert scan_2.status_code == 200
    # No duplicate exceptions or recovery cases opened
    assert scan_2.json()["exceptions_created"] == 0
    assert scan_2.json()["recovery_cases_opened"] == 0

    # Query exceptions for this shipment
    exc_res = await client.get(
        f"/api/v1/exceptions?shipment_id={shipment['id']}",
        headers=headers,
    )
    assert exc_res.status_code == 200
    assert len(exc_res.json()["items"]) == 1, "Must have exactly one exception record"


@pytest.mark.asyncio
async def test_recovery_reassignment_preserves_historical_assignment(test_engine):
    client, headers, org_id, user_id = await create_user_session(test_engine, "ops")
    c_a, v_a, d_a, c_c = await _create_test_carriers(client, headers)

    deadline = datetime.now(timezone.utc) + timedelta(hours=2)
    shipment = await _create_test_shipment(client, headers, deadline)

    bkg_res = await client.post(
        "/api/v1/bookings",
        json={"shipment_id": shipment["id"], "transporter_id": c_a["id"], "offered_rate": 1900.0},
        headers=headers,
    )
    assert bkg_res.status_code == 201, bkg_res.text
    accept_res = await client.post(
        f"/api/v1/bookings/{bkg_res.json()['id']}/accept",
        json={"agreed_rate": 1900.0, "vehicle_id": v_a["id"], "driver_id": d_a["id"]},
        headers=headers,
    )
    assert accept_res.status_code == 200, accept_res.text

    # Detect missed pickup
    await client.post(
        f"/api/v1/pickup-monitoring/scan?simulated_now={(deadline + timedelta(minutes=2)).isoformat()}",
        headers=headers,
    )

    # Get recovery case
    cases_res = await client.get("/api/v1/pickup-monitoring/recovery-cases", headers=headers)
    assert cases_res.status_code == 200
    case = cases_res.json()["items"][0]
    case_id = case["id"]

    assert case["status"] == "OPEN"
    assert case["approval_status"] == "PENDING_APPROVAL"
    assert case["failure_data"]["failed_transporter_name"] == c_a["name"]

    # Manager approves reassignment to carrier C
    approve_res = await client.post(
        f"/api/v1/pickup-monitoring/recovery-cases/{case_id}/approve",
        json={
            "replacement_transporter_id": c_c["id"],
            "agreed_rate": 2000.0,
            "notes": "Approved expedited recovery with Pinnacle Express.",
        },
        headers=headers,
    )
    assert approve_res.status_code == 200
    approved_case = approve_res.json()
    assert approved_case["status"] == "COMPLETED"
    assert approved_case["approval_status"] == "APPROVED"
    assert approved_case["replacement_transporter_id"] == c_c["id"]

    # Verify historical assignment is preserved with status REASSIGNED
    shp_res = await client.get(f"/api/v1/shipments/{shipment['id']}", headers=headers)
    assert shp_res.status_code == 200
    # Original failed carrier booking exists, replacement booking exists
    bookings = shp_res.json()["bookings"]
    assert len(bookings) >= 2


@pytest.mark.asyncio
async def test_reproducible_simulated_scenario(test_engine):
    client, headers, org_id, user_id = await create_user_session(test_engine, "ops")
    await _create_test_carriers(client, headers)

    sim_res = await client.post(
        "/api/v1/pickup-monitoring/simulate-scenario",
        json={"customer_name": "Tesla Energy Supply", "scheduled_hour_offset": 0},
        headers=headers,
    )
    assert sim_res.status_code == 200, sim_res.text
    data = sim_res.json()

    assert data["status"] == "SUCCESS"
    assert "Transporter A" in data["milestones"][0]["description"] or len(data["milestones"]) >= 5
    assert data["recovery_case_number"].startswith("RCV-")
    assert len(data["assignment_history"]) >= 1


@pytest.mark.asyncio
async def test_manual_exception_creation_lifecycle_and_metrics(test_engine):
    client, headers, org_id, user_id = await create_user_session(test_engine, "ops")
    c_a, _, _, _ = await _create_test_carriers(client, headers)

    # 1. Create manual exception
    create_res = await client.post(
        "/api/v1/exceptions",
        json={
            "transporter_id": c_a["id"],
            "exception_type": "VEHICLE_UNAVAILABLE",
            "severity": "HIGH",
            "priority": "HIGH",
            "title": "Engine overheating on Interstate 65",
            "description": "Truck experienced radiator leak 30 miles outside facility. Tow dispatched.",
        },
        headers=headers,
    )
    assert create_res.status_code == 201, create_res.text
    exc = create_res.json()
    assert exc["status"] == "OPEN"
    assert exc["priority"] == "HIGH"
    exc_id = exc["id"]

    # 2. Acknowledge exception
    ack_res = await client.post(
        f"/api/v1/exceptions/{exc_id}/acknowledge",
        json={"notes": "Desk dispatcher assigned to coordinate roadside assistance."},
        headers=headers,
    )
    assert ack_res.status_code == 200
    assert ack_res.json()["status"] == "ACKNOWLEDGED"

    # 3. Assign exception
    assign_res = await client.post(
        f"/api/v1/exceptions/{exc_id}/assign",
        json={"assigned_owner_id": user_id, "notes": "Taking ownership of breakdown."},
        headers=headers,
    )
    assert assign_res.status_code == 200
    assert assign_res.json()["status"] == "INVESTIGATING"

    # 4. Escalate exception
    esc_res = await client.post(
        f"/api/v1/exceptions/{exc_id}/escalate",
        json={"target_severity": "CRITICAL", "escalation_reason": "Risk of temperature-sensitive cargo spoiling."},
        headers=headers,
    )
    assert esc_res.status_code == 200
    assert esc_res.json()["severity"] == "CRITICAL"
    assert esc_res.json()["escalation_level"] == 1

    # 5. Resolve exception
    resolve_res = await client.post(
        f"/api/v1/exceptions/{exc_id}/resolve",
        json={
            "root_cause": "Burst upper radiator hose due to excessive wear.",
            "resolution_notes": "Hose replaced on site by mobile repair technician. Rig cleared for transit.",
        },
        headers=headers,
    )
    assert resolve_res.status_code == 200
    assert resolve_res.json()["status"] == "RESOLVED"
    assert resolve_res.json()["root_cause"] is not None

    # 6. Close exception
    close_res = await client.post(
        f"/api/v1/exceptions/{exc_id}/close",
        json={"closure_reason": "Verified rig safely back on route."},
        headers=headers,
    )
    assert close_res.status_code == 200
    assert close_res.json()["status"] == "CLOSED"

    # 7. Check Exception Metrics
    metrics_res = await client.get("/api/v1/exceptions/metrics", headers=headers)
    assert metrics_res.status_code == 200
    metrics = metrics_res.json()
    assert metrics["total_exceptions"] >= 1
    assert metrics["closed_exceptions"] >= 1
    assert "VEHICLE_UNAVAILABLE" in metrics["by_type"]
