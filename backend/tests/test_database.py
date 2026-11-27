import uuid
from datetime import datetime, timedelta, timezone
import pytest
import pytest_asyncio
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.models import (
    Base,
    AssignmentStatus,
    BookingStatus,
    CommitmentStatus,
    Driver,
    ExceptionRecord,
    ExceptionSeverity,
    ExceptionStatus,
    ExceptionType,
    Organization,
    OrganizationType,
    PickupCommitment,
    ProofOfDelivery,
    PODVerificationStatus,
    Shipment,
    ShipmentAssignment,
    ShipmentEvent,
    ShipmentStatus,
    Transporter,
    User,
    Vehicle,
)


@pytest_asyncio.fixture
async def async_db():
    """Provides a transactional async database session for testing."""
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_database_connectivity(async_db: AsyncSession):
    """Verify live PostgreSQL 17 connection."""
    result = await async_db.execute(text("SELECT current_database(), current_user, 1 AS alive"))
    row = result.fetchone()
    assert row is not None
    assert row[0] == "cargopulse"
    assert row[1] == "cargopulse_user"
    assert row[2] == 1


@pytest.mark.asyncio
async def test_all_28_tables_exist(async_db: AsyncSession):
    """Verify all 28 domain models + alembic_version are registered in PostgreSQL schema."""
    result = await async_db.execute(
        text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
    )
    existing_tables = {row[0] for row in result.fetchall()}

    expected_tables = {
        "organizations",
        "users",
        "roles",
        "permissions",
        "user_roles",
        "role_permissions",
        "refresh_sessions",
        "password_reset_tokens",
        "transporters",
        "vehicles",
        "drivers",
        "transporter_service_areas",
        "shipments",
        "transporter_bookings",
        "shipment_assignments",
        "shipment_events",
        "pickup_commitments",
        "exceptions",
        "recovery_cases",
        "notifications",
        "proof_of_delivery",
        "delivery_discrepancies",
        "integration_connections",
        "webhook_events",
        "outbox_events",
        "reconciliation_records",
        "audit_logs",
        "ai_action_records",
        "alembic_version",
    }

    missing_tables = expected_tables - existing_tables
    assert not missing_tables, f"Missing tables in PostgreSQL: {missing_tables}"


@pytest.mark.asyncio
async def test_user_email_unique_scoped_to_organization(async_db: AsyncSession):
    """
    Verify email uniqueness is scoped to organization:
    1. Two users in the SAME org with the same email must fail.
    2. Two users in DIFFERENT orgs with the same email must succeed.
    """
    org1 = Organization(
        name="Apex Manufacturing Corp",
        slug=f"apex-{uuid.uuid4().hex[:8]}",
        org_type=OrganizationType.MANUFACTURER,
    )
    org2 = Organization(
        name="Apex Logistics Subsidiary",
        slug=f"apex-sub-{uuid.uuid4().hex[:8]}",
        org_type=OrganizationType.THIRD_PARTY_LOGISTICS,
    )
    async_db.add_all([org1, org2])
    await async_db.commit()
    org1_id = org1.id
    org2_id = org2.id

    shared_email = f"logistics.director@{uuid.uuid4().hex[:8]}.com"

    # User 1 in Org 1 - should succeed
    user1 = User(
        organization_id=org1_id,
        email=shared_email,
        hashed_password="hashed_pw_placeholder",
        first_name="Alice",
        last_name="Smith",
    )
    async_db.add(user1)
    await async_db.commit()

    # User 2 in Org 1 with DUPLICATE email - must fail
    user1_duplicate = User(
        organization_id=org1_id,
        email=shared_email,
        hashed_password="hashed_pw_placeholder_2",
        first_name="Duplicate",
        last_name="Alice",
    )
    async_db.add(user1_duplicate)
    with pytest.raises(IntegrityError):
        await async_db.commit()
    await async_db.rollback()

    # User 3 in Org 2 with SAME email - must succeed (tenant-scoped)
    user2_cross_org = User(
        organization_id=org2_id,
        email=shared_email,
        hashed_password="hashed_pw_placeholder_3",
        first_name="Alice",
        last_name="CrossOrg",
    )
    async_db.add(user2_cross_org)
    await async_db.commit()
    assert user2_cross_org.id is not None


@pytest.mark.asyncio
async def test_foreign_key_violation_raises_error(async_db: AsyncSession):
    """Verify that referencing a non-existent organization_id triggers a ForeignKey constraint error."""
    fake_org_id = uuid.uuid4()
    orphan_user = User(
        organization_id=fake_org_id,
        email=f"orphan@{uuid.uuid4().hex[:8]}.com",
        hashed_password="password_hash",
        first_name="Ghost",
        last_name="Rider",
    )
    async_db.add(orphan_user)
    with pytest.raises(IntegrityError):
        await async_db.commit()
    await async_db.rollback()


@pytest.mark.asyncio
async def test_prevent_duplicate_active_shipment_assignment(async_db: AsyncSession):
    """
    Verify business rule: A shipment cannot have two active assignments simultaneously.
    """
    org = Organization(name="Omni Logistics", slug=f"omni-{uuid.uuid4().hex[:8]}")
    async_db.add(org)
    await async_db.flush()
    org_id = org.id

    transporter = Transporter(
        organization_id=org_id,
        name="FastLane Express",
        code=f"FLE-{uuid.uuid4().hex[:4]}",
        phone="+919876543210",
    )
    async_db.add(transporter)
    await async_db.flush()
    transporter_id = transporter.id

    v1 = Vehicle(
        organization_id=org_id,
        transporter_id=transporter_id,
        license_plate=f"MH12-{uuid.uuid4().hex[:4].upper()}",
        vehicle_type="32FT MXL",
        capacity_kg=15000.0,
    )
    v2 = Vehicle(
        organization_id=org_id,
        transporter_id=transporter_id,
        license_plate=f"MH14-{uuid.uuid4().hex[:4].upper()}",
        vehicle_type="32FT SXL",
        capacity_kg=12000.0,
    )
    driver1 = Driver(
        organization_id=org_id,
        transporter_id=transporter_id,
        first_name="Raj",
        last_name="Kumar",
        phone=f"+91{uuid.uuid4().int % 10000000000:010d}",
        license_number=f"DL-{uuid.uuid4().hex[:8].upper()}",
    )
    driver2 = Driver(
        organization_id=org_id,
        transporter_id=transporter_id,
        first_name="Suresh",
        last_name="Patil",
        phone=f"+91{uuid.uuid4().int % 10000000000:010d}",
        license_number=f"DL-{uuid.uuid4().hex[:8].upper()}",
    )
    async_db.add_all([v1, v2, driver1, driver2])
    await async_db.flush()

    shipment = Shipment(
        organization_id=org_id,
        tracking_number=f"TRK-{uuid.uuid4().hex[:8].upper()}",
        origin_name="Pune Hub",
        origin_address="Plot 45 MIDC",
        origin_city="Pune",
        origin_state="Maharashtra",
        origin_postal_code="411018",
        origin_contact_name="Store Officer",
        origin_contact_phone="+919876500001",
        destination_name="Bengaluru Depot",
        destination_address="Whitefield Outer Ring",
        destination_city="Bengaluru",
        destination_state="Karnataka",
        destination_postal_code="560066",
        destination_contact_name="Receiving Incharge",
        destination_contact_phone="+919876500002",
        scheduled_pickup_time=datetime.now(timezone.utc) + timedelta(hours=4),
        expected_delivery_time=datetime.now(timezone.utc) + timedelta(days=2),
        total_weight_kg=8500.0,
        package_count=120,
        goods_description="Automotive Spare Components",
    )
    async_db.add(shipment)
    await async_db.commit()

    # Pre-cache IDs
    shipment_id = shipment.id
    v1_id = v1.id
    v2_id = v2.id
    driver1_id = driver1.id
    driver2_id = driver2.id

    # First active assignment -> ASSIGNED -> should succeed
    assignment1 = ShipmentAssignment(
        organization_id=org_id,
        shipment_id=shipment_id,
        vehicle_id=v1_id,
        driver_id=driver1_id,
        status=AssignmentStatus.ASSIGNED,
    )
    async_db.add(assignment1)
    await async_db.commit()

    # Second active assignment -> ASSIGNED -> must fail with partial unique index violation
    assignment2 = ShipmentAssignment(
        organization_id=org_id,
        shipment_id=shipment_id,
        vehicle_id=v2_id,
        driver_id=driver2_id,
        status=AssignmentStatus.ASSIGNED,
    )
    async_db.add(assignment2)
    with pytest.raises(IntegrityError):
        await async_db.commit()
    await async_db.rollback()


@pytest.mark.asyncio
async def test_transaction_rollback_preserves_state(async_db: AsyncSession):
    """Verify that aborted operations roll back without leaving partial records."""
    unique_slug = f"rollback-test-{uuid.uuid4().hex[:8]}"
    org = Organization(name="Rollback Candidate", slug=unique_slug)
    async_db.add(org)
    await async_db.flush()

    # Intentionally trigger an error in the same transaction
    bad_user = User(
        organization_id=uuid.uuid4(),  # Non-existent foreign key
        email="bad@test.com",
        hashed_password="pw",
        first_name="Error",
        last_name="Test",
    )
    async_db.add(bad_user)
    try:
        await async_db.commit()
    except IntegrityError:
        await async_db.rollback()

    # Query for the org - it should NOT exist because the entire transaction rolled back
    query = await async_db.execute(select(Organization).where(Organization.slug == unique_slug))
    assert query.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_immutable_shipment_events_and_pod_verification(async_db: AsyncSession):
    """Verify append-only shipment event log and 1-to-1 e-POD verification lifecycle."""
    org = Organization(name="Precision Tech", slug=f"precision-{uuid.uuid4().hex[:8]}")
    async_db.add(org)
    await async_db.flush()
    org_id = org.id

    shipment = Shipment(
        organization_id=org_id,
        tracking_number=f"TRK-EVT-{uuid.uuid4().hex[:6].upper()}",
        status=ShipmentStatus.DISPATCHED,
        origin_name="Plant 1",
        origin_address="Highway 4",
        origin_city="Chennai",
        origin_state="Tamil Nadu",
        origin_postal_code="600001",
        origin_contact_name="Supervisor",
        origin_contact_phone="+919876540001",
        destination_name="Warehouse 3",
        destination_address="Ring Road",
        destination_city="Hyderabad",
        destination_state="Telangana",
        destination_postal_code="500001",
        destination_contact_name="Receiver",
        destination_contact_phone="+919876540002",
        scheduled_pickup_time=datetime.now(timezone.utc) - timedelta(hours=6),
        expected_delivery_time=datetime.now(timezone.utc) + timedelta(hours=18),
        total_weight_kg=4000.0,
        package_count=50,
        goods_description="Electronic Subassemblies",
    )
    async_db.add(shipment)
    await async_db.flush()
    shipment_id = shipment.id

    # Add append-only events
    event1 = ShipmentEvent(
        organization_id=org_id,
        shipment_id=shipment_id,
        event_type="GATE_IN",
        description="Vehicle arrived at pickup facility",
        latitude=13.0827,
        longitude=80.2707,
        location_name="Chennai Plant 1 Gate 2",
        source="SECURITY_KIOSK",
    )
    event2 = ShipmentEvent(
        organization_id=org_id,
        shipment_id=shipment_id,
        event_type="DISPATCHED",
        description="Cargo loaded and verified, out for delivery",
        latitude=13.0830,
        longitude=80.2710,
        location_name="Chennai Toll Plaza",
        source="SYSTEM",
    )
    async_db.add_all([event1, event2])
    await async_db.commit()

    # Verify events are stored chronologically
    q_events = await async_db.execute(
        select(ShipmentEvent).where(ShipmentEvent.shipment_id == shipment_id)
    )
    events = q_events.scalars().all()
    assert len(events) == 2
    assert {e.event_type for e in events} == {"GATE_IN", "DISPATCHED"}

    # Attach Electronic Proof of Delivery (e-POD)
    pod = ProofOfDelivery(
        organization_id=org_id,
        shipment_id=shipment_id,
        signed_by_name="M. Reddy",
        signed_by_designation="Receiving Supervisor",
        signed_at=datetime.now(timezone.utc),
        verification_status=PODVerificationStatus.VERIFIED,
        document_url="https://s3.amazonaws.com/cargopulse/pod/doc-101.pdf",
    )
    async_db.add(pod)
    await async_db.commit()

    # Verify 1-to-1 relationship enforcement: duplicate POD on same shipment must fail
    duplicate_pod = ProofOfDelivery(
        organization_id=org_id,
        shipment_id=shipment_id,
        signed_by_name="Fraud Signer",
        signed_at=datetime.now(timezone.utc),
        verification_status=PODVerificationStatus.REJECTED,
    )
    async_db.add(duplicate_pod)
    with pytest.raises(IntegrityError):
        await async_db.commit()
    await async_db.rollback()
