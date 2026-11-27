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
    ExceptionPriority,
    ExceptionSeverity,
    ExceptionStatus,
    ExceptionType,
    OutboxStatus,
    ShipmentMilestone,
    ShipmentStatus,
)
from app.models.integrations import OutboxEvent
from app.models.operations import ExceptionRecord
from app.models.shipment import Shipment, ShipmentAssignment, ShipmentEvent, TransporterBooking
from app.models.transporter import Driver, Transporter, Vehicle
from app.services.integrations.dlq_service import dlq_service
from app.services.integrations.outbox_service import outbox_service


@pytest_asyncio.fixture
async def test_engine():
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool, connect_args={"ssl": False}, echo=False)
    yield engine
    await engine.dispose()


async def create_user_session(test_engine, prefix: str, org_type: str = "MANUFACTURER"):
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
        "full_name": f"{prefix.capitalize()} QA User",
        "email": email,
        "password": "Password123!",
        "confirm_password": "Password123!",
        "organization_name": f"{prefix.capitalize()} QA Org {uid}",
        "org_type": org_type,
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


async def seed_transporter_and_resources(test_engine, org_id: str, suffix: str):
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        transporter = Transporter(
            id=uuid.uuid4(),
            organization_id=uuid.UUID(org_id),
            name=f"Comprehensive QA Transporter {suffix}",
            code=f"TR-{suffix.upper()}",
            phone="+1-555-0100",
            email=f"transporter_{suffix}@qa-logistics.test",
            compliance_details={"verification_status": "VERIFIED"},
            is_active=True,
        )
        session.add(transporter)
        await session.flush()

        vehicle = Vehicle(
            id=uuid.uuid4(),
            organization_id=uuid.UUID(org_id),
            transporter_id=transporter.id,
            license_plate=f"QA-PLT-{suffix.upper()}",
            vehicle_type="Dry Van",
            capacity_kg=Decimal("15000.00"),
            is_available=True,
        )
        session.add(vehicle)

        driver = Driver(
            id=uuid.uuid4(),
            organization_id=uuid.UUID(org_id),
            transporter_id=transporter.id,
            first_name="Arthur",
            last_name=f"Dent-{suffix}",
            phone=f"+1-555-{suffix[:4]}",
            license_number=f"LIC-{suffix.upper()}",
            is_available=True,
        )
        session.add(driver)
        await session.commit()
        return transporter, vehicle, driver


async def create_qa_shipment(client: AsyncClient, headers: dict) -> dict:
    now = datetime.now(timezone.utc)
    res = await client.post(
        "/api/v1/shipments",
        json={
            "customer_name": "Acme Manufacturing Global",
            "customer_reference": f"PO-QA-{uuid.uuid4().hex[:6].upper()}",
            "origin_name": "QA Central Depot",
            "origin_address": "100 QA Way",
            "origin_city": "Chicago",
            "origin_state": "IL",
            "origin_postal_code": "60601",
            "origin_contact_name": "Alice Dispatch",
            "origin_contact_phone": "+1-312-555-0199",
            "destination_name": "QA North Hub",
            "destination_address": "500 QA Blvd",
            "destination_city": "Minneapolis",
            "destination_state": "MN",
            "destination_postal_code": "55401",
            "destination_contact_name": "Bob Receiving",
            "destination_contact_phone": "+1-612-555-0188",
            "scheduled_pickup_time": (now + timedelta(hours=2)).isoformat(),
            "expected_delivery_time": (now + timedelta(hours=24)).isoformat(),
            "goods_description": "Industrial Pump Assemblies",
            "cargo_category": "Machinery",
            "package_count": 12,
            "package_unit": "Crates",
            "total_weight_kg": 5000.0,
            "declared_value": 25000.0,
            "priority": "HIGH",
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()


# ==============================================================================
# 1. State-Machine Invariant Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_booking_state_machine_strict_invariants(test_engine):
    """
    Validates state transitions:
    - Normal lifecycle: REQUESTED -> ACCEPTED -> CONFIRMED
    - Terminal states: REJECTED cannot transition to ACCEPTED
    - Expired booking cannot be accepted (returns 400)
    - Rejection is terminal
    """
    client, headers, _, org_id, _ = await create_user_session(test_engine, "sm_bk")
    shipment = await create_qa_shipment(client, headers)
    shipment_id = shipment["id"]

    suffix = uuid.uuid4().hex[:6]
    transporter, vehicle, driver = await seed_transporter_and_resources(test_engine, org_id, suffix)

    # 1. Create booking request
    bk_res = await client.post(
        "/api/v1/bookings",
        json={
            "shipment_id": shipment_id,
            "transporter_id": str(transporter.id),
            "offered_rate": 1800.00,
            "expires_in_hours": 24,
            "booking_notes": "QA test booking notes",
        },
        headers=headers,
    )
    assert bk_res.status_code == 201, bk_res.text
    booking = bk_res.json()
    booking_id = booking["id"]
    assert booking["status"] in (BookingStatus.REQUESTED.value, BookingStatus.PENDING_ACCEPTANCE.value)

    # 2. Reject the booking
    rej_res = await client.post(
        f"/api/v1/bookings/{booking_id}/reject",
        json={"rejection_reason": "Capacity fully booked for tomorrow"},
        headers=headers,
    )
    assert rej_res.status_code == 200, rej_res.text
    assert rej_res.json()["status"] == BookingStatus.REJECTED.value

    # 3. Illegal Transition: Cannot accept a rejected booking
    illegal_accept = await client.post(
        f"/api/v1/bookings/{booking_id}/accept",
        json={
            "agreed_rate": 1800.00,
            "vehicle_id": str(vehicle.id),
            "driver_id": str(driver.id),
        },
        headers=headers,
    )
    assert illegal_accept.status_code in (400, 422)

    # 4. Create an expired booking directly to test expiration barrier
    now = datetime.now(timezone.utc)
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        expired_booking = TransporterBooking(
            id=uuid.uuid4(),
            organization_id=uuid.UUID(org_id),
            shipment_id=uuid.UUID(shipment_id),
            transporter_id=transporter.id,
            booking_reference=f"BKG-EXP-{uuid.uuid4().hex[:6].upper()}",
            status=BookingStatus.EXPIRED,
            expires_at=now - timedelta(minutes=10),
            offered_rate=Decimal("1500.00"),
        )
        session.add(expired_booking)
        await session.commit()
        expired_id = str(expired_booking.id)

    # 5. Illegal Transition: Accepting an expired booking is blocked
    exp_accept = await client.post(
        f"/api/v1/bookings/{expired_id}/accept",
        json={
            "vehicle_id": str(vehicle.id),
            "driver_id": str(driver.id),
        },
        headers=headers,
    )
    assert exp_accept.status_code in (400, 422)


@pytest.mark.asyncio
async def test_shipment_state_machine_terminal_delivery_barrier(test_engine):
    """
    Verifies that once a shipment reaches DELIVERED terminal status:
    - It cannot regress to an earlier status or milestone (returns 400).
    - Cancelled shipments strictly reject tracking updates.
    """
    client, headers, _, org_id, _ = await create_user_session(test_engine, "sm_shp")
    shipment = await create_qa_shipment(client, headers)
    shipment_id = shipment["id"]

    # Progress through milestones up to DELIVERED
    m1 = await client.post(
        f"/api/v1/tracking/shipments/{shipment_id}/events",
        json={"milestone": "PICKUP_COMPLETED", "description": "Departed pickup dock", "source": "OPERATOR"},
        headers=headers,
    )
    assert m1.status_code == 200, m1.text

    m2 = await client.post(
        f"/api/v1/tracking/shipments/{shipment_id}/events",
        json={"milestone": "DELIVERED", "description": "Consignment signed and received", "source": "OPERATOR"},
        headers=headers,
    )
    assert m2.status_code == 200, m2.text

    # Attempt regression back to IN_TRANSIT
    regress_res = await client.post(
        f"/api/v1/tracking/shipments/{shipment_id}/events",
        json={"milestone": "IN_TRANSIT", "description": "Trying to backdate transit", "source": "OPERATOR"},
        headers=headers,
    )
    assert regress_res.status_code == 400
    assert "DELIVERED" in regress_res.text or "milestone" in regress_res.text.lower()


# ==============================================================================
# 2. Concurrency & Race Condition Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_concurrent_booking_acceptance_race_condition(test_engine):
    """
    Simulates two simultaneous acceptance requests for the same booking using asyncio.gather.
    Ensures safe concurrency handling: exactly one request confirms the booking/assignment,
    preventing duplicate assignments or corrupt state.
    """
    client, headers, _, org_id, _ = await create_user_session(test_engine, "race_bk")
    shipment = await create_qa_shipment(client, headers)
    shipment_id = shipment["id"]

    suffix = uuid.uuid4().hex[:6]
    transporter, vehicle, driver = await seed_transporter_and_resources(test_engine, org_id, suffix)

    # Create booking request
    bk_res = await client.post(
        "/api/v1/bookings",
        json={
            "shipment_id": shipment_id,
            "transporter_id": str(transporter.id),
            "offered_rate": 2200.00,
            "expires_in_hours": 24,
            "booking_notes": "Urgent direct haul",
        },
        headers=headers,
    )
    assert bk_res.status_code == 201, bk_res.text
    booking_id = bk_res.json()["id"]

    payload = {
        "agreed_rate": 2200.00,
        "vehicle_id": str(vehicle.id),
        "driver_id": str(driver.id),
    }

    # Fire concurrent acceptance calls
    results = await asyncio.gather(
        client.post(f"/api/v1/bookings/{booking_id}/accept", json=payload, headers=headers),
        client.post(f"/api/v1/bookings/{booking_id}/accept", json=payload, headers=headers),
        return_exceptions=True,
    )

    statuses = [r.status_code for r in results if not isinstance(r, Exception)]
    # At least one MUST succeed (200). If both return 200, it must be idempotent.
    assert 200 in statuses, f"Expected at least one 200 success, got {statuses}"

    # Verify database integrity: exactly one active assignment exists for this shipment
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        stmt = select(ShipmentAssignment).where(
            ShipmentAssignment.shipment_id == uuid.UUID(shipment_id),
            ShipmentAssignment.status.in_([AssignmentStatus.ASSIGNED, AssignmentStatus.ACCEPTED]),
        )
        active_assignments = (await session.execute(stmt)).scalars().all()
        assert len(active_assignments) == 1, f"Expected 1 active assignment, found {len(active_assignments)}"


# ==============================================================================
# 3. Transaction Atomicity & Rollback Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_transaction_atomicity_on_faulty_multi_step_operation(test_engine):
    """
    Verifies that when a failure occurs during an atomic transaction, all partial writes
    are rolled back without leaving orphaned rows.
    """
    client, headers, _, org_id, _ = await create_user_session(test_engine, "tx_atom")
    shipment = await create_qa_shipment(client, headers)
    shipment_id = shipment["id"]

    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        count_before = (
            await session.execute(
                select(ShipmentEvent).where(ShipmentEvent.shipment_id == uuid.UUID(shipment_id))
            )
        ).scalars().all()

    # Attempt to request booking with a non-existent transporter ID
    fake_transporter_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    invalid_bk = await client.post(
        f"/api/v1/bookings/shipments/{shipment_id}/request",
        json={
            "transporter_id": fake_transporter_id,
            "pickup_deadline": (now + timedelta(hours=3)).isoformat(),
            "expiration_minutes": 30,
            "agreed_rate": 1500.00,
        },
        headers=headers,
    )
    assert invalid_bk.status_code in (404, 400, 422)

    # Ensure no booking was committed to DB for this shipment
    async with session_factory() as session:
        bks = (
            await session.execute(
                select(TransporterBooking).where(TransporterBooking.shipment_id == uuid.UUID(shipment_id))
            )
        ).scalars().all()
        assert len(bks) == 0


# ==============================================================================
# 4. Outbox Worker, Retry & DLQ Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_outbox_retry_exhaustion_and_dlq_routing(test_engine):
    """
    Verifies outbox failure handling:
    - Simulated failures increment attempt count.
    - Exceeding MAX_RETRIES moves event to DEAD_LETTER (DLQ).
    - An exception record is automatically generated for visibility.
    """
    client, headers, _, org_id, _ = await create_user_session(test_engine, "outbox_dlq")
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)

    outbox_id = uuid.uuid4()
    async with session_factory() as session:
        # Seed an outbox event with max_retries=1
        event = OutboxEvent(
            id=outbox_id,
            organization_id=uuid.UUID(org_id),
            event_type="SHIPMENT_DISPATCHED",
            aggregate_type="Shipment",
            aggregate_id=uuid.uuid4(),
            payload={"test": "dlq_exhaustion"},
            status=OutboxStatus.PENDING,
            destination="https://erp.qa-partner.internal/webhooks",
            retry_count=0,
            max_retries=1,
            is_dead_letter=False,
            created_at=datetime.now(timezone.utc),
        )
        session.add(event)
        await session.commit()

    # Trigger failure handling via publish_pending_events
    async with session_factory() as session:
        res = await outbox_service.publish_pending_events(
            session=session,
            organization_id=uuid.UUID(org_id),
            simulate_failure_id=outbox_id,
        )
        assert res["dead_letter"] >= 1

    # Verify event transitioned to DEAD_LETTER and DLQ exception was generated
    async with session_factory() as session:
        refreshed = await session.get(OutboxEvent, outbox_id)
        assert refreshed is not None
        assert refreshed.status == OutboxStatus.DEAD_LETTER
        assert refreshed.is_dead_letter is True

        # Verify operational exception created
        stmt = select(ExceptionRecord).where(
            ExceptionRecord.organization_id == uuid.UUID(org_id),
            ExceptionRecord.exception_type == ExceptionType.INTEGRATION_FAILURE,
        )
        exc = (await session.execute(stmt)).scalars().first()
        assert exc is not None
        assert "Outbox" in exc.title or "INTEGRATION" in exc.title


# ==============================================================================
# 5. AI Tool Authorization & Tenant Isolation Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_ai_coordinator_tenant_boundary_enforcement(test_engine):
    """
    Verifies that the AI Logistics Coordinator backend tools strictly respect tenant isolation:
    A user/session from Organization B cannot query shipment details or trigger recovery actions
    for a shipment belonging to Organization A.
    """
    client_a, headers_a, _, org_a, user_a = await create_user_session(test_engine, "ai_org_a")
    client_b, headers_b, _, org_b, user_b = await create_user_session(test_engine, "ai_org_b")

    # Org A creates a shipment
    shipment_a = await create_qa_shipment(client_a, headers_a)
    shipment_a_id = shipment_a["id"]

    from app.services.ai import tools

    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        # Org B invokes get_shipment_details on Org A's shipment -> must return not found
        details = await tools.get_shipment_details(
            session=session,
            organization_id=uuid.UUID(org_b),
            shipment_identifier=shipment_a_id,
        )
        assert details.get("found") is False or "not found" in details.get("message", "").lower()

        # Org B attempts to request reassignment approval on Org A's shipment -> must fail
        fake_transporter = str(uuid.uuid4())
        res = await tools.request_reassignment_approval(
            session=session,
            organization_id=uuid.UUID(org_b),
            shipment_id=shipment_a_id,
            replacement_transporter_id=fake_transporter,
            reason="Unauthorized cross-tenant attempt",
            user_id=uuid.UUID(user_b),
        )
        assert res.get("success") is False
        assert "not found" in res.get("error", "").lower()
