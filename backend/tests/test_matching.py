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
from app.models.enums import BookingStatus, ShipmentStatus
from app.models.shipment import Shipment, TransporterBooking
from app.models.transporter import Driver, Transporter, TransporterServiceArea, Vehicle


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
        "organization_name": f"{prefix.capitalize()} Freight {uid}",
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


async def create_test_shipment(client, headers, weight_kg=15000.0, vehicle_type="53' Dry Van"):
    now = datetime.now(timezone.utc)
    payload = {
        "customer_name": "General Motors Assembly",
        "customer_reference": "GM-PO-8821",
        "origin_name": "Chicago Logistics Hub",
        "origin_address": "4500 S Cicero Ave",
        "origin_city": "Chicago",
        "origin_state": "IL",
        "origin_postal_code": "60638",
        "origin_contact_name": "Bob Warehouse",
        "origin_contact_phone": "+1-312-555-0199",
        "destination_name": "Detroit Stamping Plant",
        "destination_address": "2500 E Grand Blvd",
        "destination_city": "Detroit",
        "destination_state": "MI",
        "destination_postal_code": "48211",
        "destination_contact_name": "Alice Receiving",
        "destination_contact_phone": "+1-313-555-0188",
        "goods_description": "Stamped sheet metal body panels",
        "cargo_category": "Automotive Parts",
        "total_weight_kg": weight_kg,
        "package_count": 24,
        "package_unit": "Pallets",
        "required_vehicle_type": vehicle_type,
        "priority": "HIGH",
        "scheduled_pickup_time": (now + timedelta(days=1)).isoformat(),
        "expected_delivery_time": (now + timedelta(days=2)).isoformat(),
    }
    resp = await client.post("/api/v1/shipments", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.mark.asyncio
async def test_hard_filter_unverified_and_suspended_transporters_excluded(test_engine):
    """
    Test Step 1 Hard Eligibility Filters:
    Unverified carriers (REGISTERED, UNDER_VERIFICATION) and SUSPENDED carriers are excluded.
    """
    client, user, headers, _ = await create_user_session(test_engine, "match_filter")

    # 1. Create a shipment
    shipment = await create_test_shipment(client, headers, weight_kg=10000.0)
    shipment_id = shipment["id"]

    # 2. Create an unverified carrier
    c1_resp = await client.post(
        "/api/v1/transporters",
        json={
            "name": "Unverified Carrier LLC",
            "phone": "+1-312-555-0101",
            "service_regions": ["IL", "MI"],
        },
        headers=headers,
    )
    assert c1_resp.status_code == 201
    c1_id = c1_resp.json()["id"]

    # Add vehicle to c1
    await client.post(
        "/api/v1/vehicles",
        json={
            "transporter_id": c1_id,
            "license_plate": f"UNVER-{uuid.uuid4().hex[:4].upper()}",
            "vehicle_type": "53' Dry Van",
            "capacity_kg": 20000.0,
        },
        headers=headers,
    )

    # 3. Create a suspended carrier
    c2_resp = await client.post(
        "/api/v1/transporters",
        json={
            "name": "Suspended Carrier LLC",
            "phone": "+1-312-555-0102",
            "service_regions": ["IL", "MI"],
        },
        headers=headers,
    )
    assert c2_resp.status_code == 201
    c2_id = c2_resp.json()["id"]

    # Suspend c2
    await client.post(f"/api/v1/transporters/{c2_id}/suspend?reason=Failed+audit", headers=headers)

    # 4. Request matching recommendations
    match_resp = await client.get(f"/api/v1/shipments/{shipment_id}/match", headers=headers)
    assert match_resp.status_code == 200, match_resp.text
    data = match_resp.json()

    assert data["shipment_id"] == shipment_id
    assert data["total_carriers_evaluated"] >= 2

    # Unverified and Suspended must NOT be in eligible recommendations
    eligible_ids = [r["transporter_id"] for r in data["recommendations"]]
    assert c1_id not in eligible_ids
    assert c2_id not in eligible_ids

    # Check excluded list contains them with transparent reasons
    excluded_ids = [r["transporter_id"] for r in data["excluded"]]
    assert c1_id in excluded_ids
    assert c2_id in excluded_ids

    c1_rec = next(r for r in data["excluded"] if r["transporter_id"] == c1_id)
    assert any("must be VERIFIED" in reason for reason in c1_rec["ineligibility_reasons"])

    c2_rec = next(r for r in data["excluded"] if r["transporter_id"] == c2_id)
    assert any("suspended" in reason.lower() for reason in c2_rec["ineligibility_reasons"])


@pytest.mark.asyncio
async def test_hard_filter_insufficient_capacity_and_expired_documents(test_engine):
    """
    Test Step 1 Hard Eligibility Filters:
    - Carrier with vehicles having capacity < shipment weight is excluded.
    - Carrier with expired insurance/fitness documents is excluded.
    """
    client, user, headers, _ = await create_user_session(test_engine, "match_cap_doc")

    # 1. Create a 25,000 kg shipment
    shipment = await create_test_shipment(client, headers, weight_kg=25000.0)
    shipment_id = shipment["id"]

    # 2. Create Verified Carrier A (only has 18,000 kg vehicle)
    ca_resp = await client.post(
        "/api/v1/transporters",
        json={"name": "Light Fleet Express", "phone": "+1-312-555-0201", "service_regions": ["IL", "MI"]},
        headers=headers,
    )
    ca_id = ca_resp.json()["id"]
    await client.post(
        f"/api/v1/transporters/{ca_id}/verify",
        json={"status": "VERIFIED", "verification_notes": "Docs checked"},
        headers=headers,
    )
    await client.post(
        "/api/v1/vehicles",
        json={
            "transporter_id": ca_id,
            "license_plate": f"LIGHT-{uuid.uuid4().hex[:4].upper()}",
            "vehicle_type": "53' Dry Van",
            "capacity_kg": 18000.0,  # Insufficient!
        },
        headers=headers,
    )

    # 3. Create Verified Carrier B (has 30,000 kg vehicle, BUT expired insurance)
    cb_resp = await client.post(
        "/api/v1/transporters",
        json={"name": "Expired Docs Freight", "phone": "+1-312-555-0202", "service_regions": ["IL", "MI"]},
        headers=headers,
    )
    cb_id = cb_resp.json()["id"]
    await client.post(
        f"/api/v1/transporters/{cb_id}/verify",
        json={"status": "VERIFIED", "verification_notes": "Docs checked"},
        headers=headers,
    )
    await client.post(
        "/api/v1/vehicles",
        json={
            "transporter_id": cb_id,
            "license_plate": f"EXP-{uuid.uuid4().hex[:4].upper()}",
            "vehicle_type": "53' Dry Van",
            "capacity_kg": 30000.0,
            "insurance_expiry": (datetime.now(timezone.utc) - timedelta(days=10)).isoformat(),  # EXPIRED!
        },
        headers=headers,
    )

    # 4. Request matching recommendations
    match_resp = await client.get(f"/api/v1/shipments/{shipment_id}/match", headers=headers)
    assert match_resp.status_code == 200
    data = match_resp.json()

    eligible_ids = [r["transporter_id"] for r in data["recommendations"]]
    assert ca_id not in eligible_ids
    assert cb_id not in eligible_ids

    ca_rec = next(r for r in data["excluded"] if r["transporter_id"] == ca_id)
    assert any("capacity >= 25000.0kg" in reason for reason in ca_rec["ineligibility_reasons"])

    cb_rec = next(r for r in data["excluded"] if r["transporter_id"] == cb_id)
    assert any("valid documentation" in reason for reason in cb_rec["ineligibility_reasons"])


@pytest.mark.asyncio
async def test_scoring_ranking_and_scorecard_breakdown(test_engine):
    """
    Test Step 2: Scoring model weights and ranking.
    Verified carrier with dedicated lane & high performance outranks partial carrier.
    Verifies scorecard weights:
    - Pickup Reliability: 40%
    - On-Time Delivery: 25%
    - Booking Acceptance: 15%
    - Route Suitability: 10%
    - Cost Competitiveness: 10%
    """
    client, user, headers, _ = await create_user_session(test_engine, "match_scoring")

    # 1. Create shipment
    shipment = await create_test_shipment(client, headers, weight_kg=12000.0)
    shipment_id = shipment["id"]

    # 2. Carrier Alpha: Direct Lane + High Reliability
    alpha_resp = await client.post(
        "/api/v1/transporters",
        json={
            "name": "Alpha Dedicated Linehaul",
            "phone": "+1-312-555-0301",
            "service_regions": ["IL", "MI"],
        },
        headers=headers,
    )
    alpha_id = alpha_resp.json()["id"]
    await client.post(
        f"/api/v1/transporters/{alpha_id}/verify",
        json={"status": "VERIFIED", "verification_notes": "Tier 1 carrier"},
        headers=headers,
    )
    # Map direct dedicated lane
    await client.post(
        f"/api/v1/transporters/{alpha_id}/service-areas",
        json={
            "origin_region": "Chicago, IL",
            "destination_region": "Detroit, MI",
            "estimated_transit_hours": 6,
        },
        headers=headers,
    )
    # Add eligible vehicle
    await client.post(
        "/api/v1/vehicles",
        json={
            "transporter_id": alpha_id,
            "license_plate": f"ALPHA-{uuid.uuid4().hex[:4].upper()}",
            "vehicle_type": "53' Dry Van",
            "capacity_kg": 20000.0,
        },
        headers=headers,
    )

    # 3. Carrier Beta: Regional carrier without direct corridor
    beta_resp = await client.post(
        "/api/v1/transporters",
        json={
            "name": "Beta Regional Haul",
            "phone": "+1-312-555-0302",
            "service_regions": ["IL"],  # Partial regional
        },
        headers=headers,
    )
    beta_id = beta_resp.json()["id"]
    await client.post(
        f"/api/v1/transporters/{beta_id}/verify",
        json={"status": "VERIFIED", "verification_notes": "Tier 2 carrier"},
        headers=headers,
    )
    await client.post(
        "/api/v1/vehicles",
        json={
            "transporter_id": beta_id,
            "license_plate": f"BETA-{uuid.uuid4().hex[:4].upper()}",
            "vehicle_type": "53' Dry Van",
            "capacity_kg": 20000.0,
        },
        headers=headers,
    )

    # 4. Run Matching
    match_resp = await client.get(f"/api/v1/shipments/{shipment_id}/match", headers=headers)
    assert match_resp.status_code == 200
    data = match_resp.json()

    assert data["eligible_carriers_count"] >= 2
    recs = data["recommendations"]

    # Verify Alpha is ranked #1 because of direct lane suitability (100 vs 65)
    alpha_rec = next(r for r in recs if r["transporter_id"] == alpha_id)
    beta_rec = next(r for r in recs if r["transporter_id"] == beta_id)

    assert alpha_rec["rank"] < beta_rec["rank"]
    assert alpha_rec["match_score"] > beta_rec["match_score"]
    assert alpha_rec["route_suitability_type"] == "DIRECT_LANE"

    # Verify Scorecard weights and components
    scorecard = alpha_rec["scorecard"]
    assert scorecard["pickup_reliability"]["weight"] == 0.40
    assert scorecard["ontime_delivery"]["weight"] == 0.25
    assert scorecard["booking_acceptance"]["weight"] == 0.15
    assert scorecard["route_suitability"]["weight"] == 0.10
    assert scorecard["cost_competitiveness"]["weight"] == 0.10

    assert scorecard["route_suitability"]["score"] == 100.0
    assert scorecard["route_suitability"]["weighted_score"] == 10.0


@pytest.mark.asyncio
async def test_new_transporter_baseline_handling(test_engine):
    """
    Test Step 2: New transporters with zero historical deliveries receive
    neutral baseline priors and are flagged with is_new_transporter == True.
    """
    client, user, headers, _ = await create_user_session(test_engine, "match_new_carrier")

    shipment = await create_test_shipment(client, headers)
    shipment_id = shipment["id"]

    # Create brand new verified carrier with 0 trips
    new_resp = await client.post(
        "/api/v1/transporters",
        json={"name": "Apex Fresh Logistics", "phone": "+1-312-555-0401", "service_regions": ["IL", "MI"]},
        headers=headers,
    )
    new_id = new_resp.json()["id"]
    await client.post(
        f"/api/v1/transporters/{new_id}/verify",
        json={"status": "VERIFIED", "verification_notes": "Initial vetting approved"},
        headers=headers,
    )
    await client.post(
        "/api/v1/vehicles",
        json={
            "transporter_id": new_id,
            "license_plate": f"NEW-{uuid.uuid4().hex[:4].upper()}",
            "vehicle_type": "53' Dry Van",
            "capacity_kg": 22000.0,
        },
        headers=headers,
    )

    match_resp = await client.get(f"/api/v1/shipments/{shipment_id}/match", headers=headers)
    assert match_resp.status_code == 200
    data = match_resp.json()

    new_rec = next(r for r in data["recommendations"] if r["transporter_id"] == new_id)
    assert new_rec["is_new_transporter"] is True
    assert "New partner" in new_rec["recommendation_summary"]

    # Baseline scores verified
    scorecard = new_rec["scorecard"]
    assert scorecard["pickup_reliability"]["score"] == 75.0
    assert scorecard["ontime_delivery"]["score"] == 75.0
    assert scorecard["booking_acceptance"]["score"] == 80.0


@pytest.mark.asyncio
async def test_dispatch_manager_manual_selection_and_audit(test_engine):
    """
    Test Step 4: Dispatch Manager manual selection of recommended transporter.
    - Creates TransporterBooking tender
    - Updates Shipment status to PENDING_ACCEPTANCE and assigned_transporter_id
    - Appends ShipmentEvent
    - Updates AIActionRecord approval metadata
    - Validates against selecting for cancelled shipments.
    """
    client, user, headers, _ = await create_user_session(test_engine, "match_select")

    shipment = await create_test_shipment(client, headers)
    shipment_id = shipment["id"]

    # Create and verify carrier with vehicle & driver
    carrier_resp = await client.post(
        "/api/v1/transporters",
        json={"name": "Committed Logistics LLC", "phone": "+1-312-555-0501", "service_regions": ["IL", "MI"]},
        headers=headers,
    )
    carrier_id = carrier_resp.json()["id"]
    await client.post(
        f"/api/v1/transporters/{carrier_id}/verify",
        json={"status": "VERIFIED", "verification_notes": "Approved"},
        headers=headers,
    )
    v_resp = await client.post(
        "/api/v1/vehicles",
        json={
            "transporter_id": carrier_id,
            "license_plate": f"SEL-{uuid.uuid4().hex[:4].upper()}",
            "vehicle_type": "53' Dry Van",
            "capacity_kg": 20000.0,
        },
        headers=headers,
    )
    vehicle_id = v_resp.json()["id"]

    d_resp = await client.post(
        "/api/v1/drivers",
        json={
            "transporter_id": carrier_id,
            "first_name": "Marcus",
            "last_name": "Vance",
            "phone": "+1-312-555-0599",
            "license_number": "DL-998811-IL",
        },
        headers=headers,
    )
    driver_id = d_resp.json()["id"]

    # 1. Trigger recommendation to create AIActionRecord
    await client.get(f"/api/v1/shipments/{shipment_id}/match", headers=headers)

    # 2. Select transporter manually
    select_payload = {
        "transporter_id": carrier_id,
        "vehicle_id": vehicle_id,
        "driver_id": driver_id,
        "agreed_rate": 1250.0,
        "booking_notes": "Special instructions: Temperature check required at dock.",
    }
    sel_resp = await client.post(
        f"/api/v1/shipments/{shipment_id}/match/select",
        json=select_payload,
        headers=headers,
    )
    assert sel_resp.status_code == 200, sel_resp.text
    sel_data = sel_resp.json()

    assert sel_data["success"] is True
    assert sel_data["shipment_id"] == shipment_id
    assert sel_data["transporter_id"] == carrier_id
    assert sel_data["booking_id"] is not None
    assert sel_data["assignment_id"] is not None
    assert sel_data["agreed_rate"] == 1250.0
    assert sel_data["shipment_status"] == "PENDING_ACCEPTANCE"

    # 3. Check shipment detail reflects assigned transporter
    shp_resp = await client.get(f"/api/v1/shipments/{shipment_id}", headers=headers)
    assert shp_resp.status_code == 200
    shp_detail = shp_resp.json()
    assert shp_detail["assigned_transporter_id"] == carrier_id
    assert shp_detail["status"] == "PENDING_ACCEPTANCE"
    assert len(shp_detail["bookings"]) >= 1

    # 4. Prevent selecting for cancelled shipments
    # Cancel shipment
    await client.post(
        f"/api/v1/shipments/{shipment_id}/cancel",
        json={"cancellation_reason": "Order cancelled by customer"},
        headers=headers,
    )
    # Attempt selection again -> should fail with 400
    fail_resp = await client.post(
        f"/api/v1/shipments/{shipment_id}/match/select",
        json=select_payload,
        headers=headers,
    )
    assert fail_resp.status_code == 400
    assert "Cannot assign transporter to shipment in status 'CANCELLED'" in fail_resp.json()["detail"]


@pytest.mark.asyncio
async def test_cross_tenant_isolation_on_matching(test_engine):
    """
    IDOR Security: Organization B cannot match or select shipments belonging to Organization A.
    """
    client_a, _, headers_a, _ = await create_user_session(test_engine, "tenant_a")
    client_b, _, headers_b, _ = await create_user_session(test_engine, "tenant_b")

    # Create shipment in Org A
    shipment_a = await create_test_shipment(client_a, headers_a)
    shipment_a_id = shipment_a["id"]

    # Org B attempts to match Org A shipment -> 404
    match_b = await client_b.get(f"/api/v1/shipments/{shipment_a_id}/match", headers=headers_b)
    assert match_b.status_code == 404

    # Org B attempts to select Org A shipment -> 404
    select_b = await client_b.post(
        f"/api/v1/shipments/{shipment_a_id}/match/select",
        json={"transporter_id": str(uuid.uuid4())},
        headers=headers_b,
    )
    assert select_b.status_code == 404
