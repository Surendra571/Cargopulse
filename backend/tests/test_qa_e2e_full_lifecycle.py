import asyncio
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
    ExceptionStatus,
    ExceptionType,
    ShipmentMilestone,
    ShipmentStatus,
)
from app.models.operations import ExceptionRecord
from app.models.shipment import PickupCommitment, Shipment, ShipmentAssignment, TransporterBooking
from app.models.transporter import Driver, Transporter, Vehicle
from app.services.pickup_monitoring_service import PickupMonitoringService


@pytest_asyncio.fixture
async def test_engine():
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool, connect_args={"ssl": False}, echo=False)
    yield engine
    await engine.dispose()


@pytest.mark.asyncio
async def test_e2e_complete_17_step_logistics_lifecycle(test_engine):
    """
    Executes the comprehensive 17-step end-to-end logistics lifecycle scenario:
    1. Register and log in.
    2. Create organization.
    3. Create shipment.
    4. Register transporter.
    5. Match transporter.
    6. Create booking.
    7. Accept booking.
    8. Simulate missed pickup.
    9. Detect exception.
    10. Approve recovery.
    11. Complete replacement booking.
    12. Record pickup.
    13. Update tracking.
    14. Submit POD.
    15. Reconcile shipment.
    16. Verify analytics.
    17. Verify audit history.
    """
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

    # =========================================================================
    # Step 1 & 2: Register User & Create Organization
    # =========================================================================
    uid = uuid.uuid4().hex[:6]
    user_email = f"e2e_lead_{uid}@apex-industrial.com"
    reg_res = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "E2E Operations Director",
            "email": user_email,
            "password": "Password123!",
            "confirm_password": "Password123!",
            "organization_name": f"Apex Industrial Global {uid}",
            "org_type": "MANUFACTURER",
            "accept_terms": True,
        },
    )
    assert reg_res.status_code == 201, reg_res.text
    auth_data = reg_res.json()
    token = auth_data["access_token"]
    user_id = auth_data["user"]["id"]
    org_id = auth_data["user"]["organization_id"]
    csrf_token = reg_res.cookies.get(settings.COOKIE_CSRF_NAME)

    headers = {"Authorization": f"Bearer {token}"}
    if csrf_token:
        headers["X-CSRF-Token"] = csrf_token

    # Verify authentication /me
    me_res = await client.get("/api/v1/auth/me", headers=headers)
    assert me_res.status_code == 200
    assert me_res.json()["email"] == user_email

    # =========================================================================
    # Step 3: Create Shipment
    # =========================================================================
    now = datetime.now(timezone.utc)
    past_pickup = now - timedelta(hours=2)  # In past to simulate overdue pickup in step 8
    future_delivery = now + timedelta(days=2)

    shp_res = await client.post(
        "/api/v1/shipments",
        json={
            "customer_name": "Boeing Aerostructures",
            "customer_reference": f"BA-PO-{uid.upper()}",
            "origin_name": "Apex Plant 4",
            "origin_address": "400 Aerospace Way",
            "origin_city": "Wichita",
            "origin_state": "KS",
            "origin_postal_code": "67210",
            "origin_contact_name": "Dave Dispatch",
            "origin_contact_phone": "+1-316-555-0199",
            "destination_name": "Boeing Final Assembly",
            "destination_address": "1000 Assembly Blvd",
            "destination_city": "Seattle",
            "destination_state": "WA",
            "destination_postal_code": "98108",
            "destination_contact_name": "Sarah Intake",
            "destination_contact_phone": "+1-206-555-0188",
            "scheduled_pickup_time": past_pickup.isoformat(),
            "expected_delivery_time": future_delivery.isoformat(),
            "goods_description": "Titanium Wing Spar Components",
            "cargo_category": "Aerospace",
            "package_count": 10,
            "package_unit": "Pallets",
            "total_weight_kg": 6000.0,
            "declared_value": 350000.0,
            "priority": "HIGH",
        },
        headers=headers,
    )
    assert shp_res.status_code == 201, shp_res.text
    shipment = shp_res.json()
    shipment_id = shipment["id"]
    tracking_number = shipment["tracking_number"]

    # =========================================================================
    # Step 4: Register Transporters (Transporter A & Replacement Transporter B)
    # =========================================================================
    async with session_factory() as session:
        # Carrier A (Original)
        t_a = Transporter(
            id=uuid.uuid4(),
            organization_id=uuid.UUID(org_id),
            name=f"Midwest Haulers A {uid}",
            code=f"MHA-{uid.upper()}",
            phone="+1-555-0101",
            email=f"dispatch_a_{uid}@midwest-haulers.test",
            compliance_details={"verification_status": "VERIFIED"},
            is_active=True,
        )
        session.add(t_a)
        await session.flush()

        v_a = Vehicle(
            id=uuid.uuid4(),
            organization_id=uuid.UUID(org_id),
            transporter_id=t_a.id,
            license_plate=f"KS-V1-{uid.upper()}",
            vehicle_type="Dry Van",
            capacity_kg=Decimal("15000.00"),
            is_available=True,
        )
        d_a = Driver(
            id=uuid.uuid4(),
            organization_id=uuid.UUID(org_id),
            transporter_id=t_a.id,
            first_name="Hank",
            last_name="Hill",
            phone=f"+1-555-11{uid[:2]}",
            license_number=f"CDL-A-{uid.upper()}",
            is_available=True,
        )
        session.add_all([v_a, d_a])

        # Carrier B (Replacement)
        t_b = Transporter(
            id=uuid.uuid4(),
            organization_id=uuid.UUID(org_id),
            name=f"Pacific Express B {uid}",
            code=f"PEB-{uid.upper()}",
            phone="+1-555-0202",
            email=f"dispatch_b_{uid}@pacific-express.test",
            compliance_details={"verification_status": "VERIFIED"},
            is_active=True,
        )
        session.add(t_b)
        await session.flush()

        v_b = Vehicle(
            id=uuid.uuid4(),
            organization_id=uuid.UUID(org_id),
            transporter_id=t_b.id,
            license_plate=f"WA-V2-{uid.upper()}",
            vehicle_type="Dry Van",
            capacity_kg=Decimal("18000.00"),
            is_available=True,
        )
        d_b = Driver(
            id=uuid.uuid4(),
            organization_id=uuid.UUID(org_id),
            transporter_id=t_b.id,
            first_name="Peggy",
            last_name="Hill",
            phone=f"+1-555-22{uid[:2]}",
            license_number=f"CDL-B-{uid.upper()}",
            is_available=True,
        )
        session.add_all([v_b, d_b])
        await session.commit()

        t_a_id = str(t_a.id)
        v_a_id = str(v_a.id)
        d_a_id = str(d_a.id)
        t_b_id = str(t_b.id)
        v_b_id = str(v_b.id)
        d_b_id = str(d_b.id)

    # =========================================================================
    # Step 5: Match Transporter
    # =========================================================================
    match_res = await client.get(
        f"/api/v1/shipments/{shipment_id}/match",
        headers=headers,
    )
    assert match_res.status_code == 200, match_res.text
    match_data = match_res.json()
    assert "recommendations" in match_data
    assert "total_carriers_evaluated" in match_data

    # =========================================================================
    # Step 6: Create Booking (Transporter A)
    # =========================================================================
    bkg_res = await client.post(
        "/api/v1/bookings",
        json={
            "shipment_id": shipment_id,
            "transporter_id": t_a_id,
            "offered_rate": 3200.00,
            "expires_in_hours": 24,
            "booking_notes": "Expedited aerospace components",
        },
        headers=headers,
    )
    assert bkg_res.status_code == 201, bkg_res.text
    bkg_a_id = bkg_res.json()["id"]

    # =========================================================================
    # Step 7: Accept Booking (Carrier A Confirms)
    # =========================================================================
    accept_res = await client.post(
        f"/api/v1/bookings/{bkg_a_id}/accept",
        json={
            "agreed_rate": 3200.00,
            "vehicle_id": v_a_id,
            "driver_id": d_a_id,
            "response_notes": "Unit KS-V1 dispatched to Wichita dock.",
        },
        headers=headers,
    )
    assert accept_res.status_code == 200, accept_res.text
    assert accept_res.json()["status"] == BookingStatus.CONFIRMED.value

    # Verify Shipment status is COMMITTED
    shp_committed = (await client.get(f"/api/v1/shipments/{shipment_id}", headers=headers)).json()
    assert shp_committed["status"] == ShipmentStatus.COMMITTED.value

    # =========================================================================
    # Step 8: Simulate Missed Pickup
    # =========================================================================
    # Adjust pickup commitment deadline to 1 hour in the past to trigger overdue condition
    async with session_factory() as session:
        cmt = (
            await session.execute(
                select(PickupCommitment).where(PickupCommitment.shipment_id == uuid.UUID(shipment_id))
            )
        ).scalar_one_or_none()
        if cmt:
            cmt.pickup_deadline = now - timedelta(hours=1)
            cmt.status = CommitmentStatus.CONFIRMED
            await session.commit()

        # Execute scheduled background monitoring scan
        scan_res = await PickupMonitoringService.monitor_commitments(
            session=session,
            organization_id=uuid.UUID(org_id),
            simulated_now=now + timedelta(hours=1),
        )
        assert scan_res.scanned_count >= 1

    # =========================================================================
    # Step 9: Detect Exception
    # =========================================================================
    exc_res = await client.get(f"/api/v1/exceptions?shipment_id={shipment_id}", headers=headers)
    assert exc_res.status_code == 200, exc_res.text
    exceptions = exc_res.json()["items"]
    assert len(exceptions) >= 1
    overdue_exc = exceptions[0]
    assert overdue_exc["exception_type"] in (ExceptionType.PICKUP_OVERDUE.value, ExceptionType.MISSED_PICKUP.value)

    # =========================================================================
    # Step 10: Approve Recovery (AI Logistics Coordinator Proposes Reassignment)
    # =========================================================================
    async with session_factory() as session:
        from app.services.ai import tools
        reassign_proposal = await tools.request_reassignment_approval(
            session=session,
            organization_id=uuid.UUID(org_id),
            shipment_id=shipment_id,
            replacement_transporter_id=t_b_id,
            reason="Original carrier missed Wichita pickup SLA buffer",
            additional_cost=250.00,
            user_id=uuid.UUID(user_id),
        )
        assert reassign_proposal["success"] is True
        action_id = uuid.UUID(reassign_proposal["action_id"])

        # Operations manager approves the recovery action
        from app.services.ai.coordinator_service import AICoordinatorService
        appr_res = await AICoordinatorService.approve_action(
            session=session,
            action_id=action_id,
            user_id=uuid.UUID(user_id),
            organization_id=uuid.UUID(org_id),
            approval_notes="Approved urgent reassignment to Pacific Express B",
        )
        assert appr_res["success"] is True

    # =========================================================================
    # Step 11: Complete Replacement Booking (Transporter B)
    # =========================================================================
    # Carrier B accepts with vehicle and driver
    async with session_factory() as session:
        # Fetch the newly generated booking for Transporter B
        b2 = (
            await session.execute(
                select(TransporterBooking).where(
                    TransporterBooking.shipment_id == uuid.UUID(shipment_id),
                    TransporterBooking.transporter_id == uuid.UUID(t_b_id),
                )
            )
        ).scalars().first()
        assert b2 is not None
        bkg_b_id = str(b2.id)

    accept_b_res = await client.post(
        f"/api/v1/bookings/{bkg_b_id}/accept",
        json={
            "agreed_rate": 3450.00,
            "vehicle_id": v_b_id,
            "driver_id": d_b_id,
            "response_notes": "Unit WA-V2 on dock at Wichita plant.",
        },
        headers=headers,
    )
    assert accept_b_res.status_code == 200
    assert accept_b_res.json()["status"] == BookingStatus.CONFIRMED.value

    # =========================================================================
    # Step 12: Record Pickup
    # =========================================================================
    pickup_time = now + timedelta(minutes=15)
    pickup_res = await client.post(
        f"/api/v1/tracking/shipments/{shipment_id}/events",
        json={
            "milestone": "PICKUP_COMPLETED",
            "event_type": "PICKUP_COMPLETED",
            "description": "Cargo inspected and loaded onto trailer WA-V2",
            "occurred_at": pickup_time.isoformat(),
            "location_name": "Wichita Plant 4 Dock Bay 3",
            "source": "DRIVER",
        },
        headers=headers,
    )
    assert pickup_res.status_code == 200, pickup_res.text

    # =========================================================================
    # Step 13: Update Tracking (Milestones In-Transit)
    # =========================================================================
    transit_res = await client.post(
        f"/api/v1/tracking/shipments/{shipment_id}/events",
        json={
            "milestone": "IN_TRANSIT",
            "description": "Rolling north on I-35 through Salina",
            "location_name": "Salina Weigh Station",
            "latitude": 38.8403,
            "longitude": -97.6114,
            "source": "TELEMATICS",
        },
        headers=headers,
    )
    assert transit_res.status_code == 200

    checkpoint_res = await client.post(
        f"/api/v1/tracking/shipments/{shipment_id}/events",
        json={
            "milestone": "CHECKPOINT_REACHED",
            "description": "Passed Spokane Port of Entry",
            "location_name": "Spokane Freight Depot",
            "latitude": 47.6588,
            "longitude": -117.4260,
            "source": "TELEMATICS",
        },
        headers=headers,
    )
    assert checkpoint_res.status_code == 200

    # =========================================================================
    # Step 14: Submit Proof of Delivery (POD)
    # =========================================================================
    delivery_time = now + timedelta(hours=36)
    pod_res = await client.post(
        f"/api/v1/pod/shipments/{shipment_id}/submit",
        json={
            "recipient_name": "Sarah Intake",
            "recipient_designation": "Receiving Dock Supervisor",
            "recipient_phone": "+1-206-555-0188",
            "received_quantity": 10,
            "delivery_photo_urls": ["s3://cargopulse-pod/photo1.jpg", "s3://cargopulse-pod/photo2.jpg"],
            "signature_image_url": "s3://cargopulse-pod/sig_sarah.png",
            "delivery_location_name": "Boeing Final Assembly Dock 14",
            "delivered_at": delivery_time.isoformat(),
        },
        headers=headers,
    )
    assert pod_res.status_code in (200, 201), pod_res.text
    pod_data = pod_res.json()
    assert pod_data["verification_status"] in ("PENDING", "VERIFIED")

    # Verify Shipment status transitioned to DELIVERED
    delivered_shp = (await client.get(f"/api/v1/shipments/{shipment_id}", headers=headers)).json()
    assert delivered_shp["status"] == ShipmentStatus.DELIVERED.value

    # =========================================================================
    # Step 15: Reconcile Shipment
    # =========================================================================
    rec_res = await client.get(f"/api/v1/reconciliation/{shipment_id}", headers=headers)
    assert rec_res.status_code == 200, rec_res.text
    rec_data = rec_res.json()
    assert "comparison" in rec_data or "reconciliation" in rec_data or "items" in rec_data

    # =========================================================================
    # Step 16: Verify Analytics
    # =========================================================================
    analytics_res = await client.get("/api/v1/analytics/overview", headers=headers)
    assert analytics_res.status_code == 200, analytics_res.text
    metrics = analytics_res.json()
    assert metrics["total_shipments"] >= 1
    assert metrics["successful_pickups"] >= 1

    transporter_analytics = await client.get("/api/v1/analytics/transporters", headers=headers)
    assert transporter_analytics.status_code == 200
    assert len(transporter_analytics.json()) >= 1

    # =========================================================================
    # Step 17: Verify Audit History
    # =========================================================================
    audit_res = await client.get("/api/v1/audit/logs", headers=headers)
    assert audit_res.status_code == 200, audit_res.text
    audit_logs = audit_res.json()["items"]
    actions_recorded = [log["action"] for log in audit_logs]

    # Verify key audit trail events are present
    assert any("REGISTER" in act or "USER" in act for act in actions_recorded)
    assert any("SHIPMENT" in act or "MILESTONE" in act or "POD" in act for act in actions_recorded)
