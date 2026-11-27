"""
Tests for Phase 17: CargoPulse Reconciliation Center
Validates:
1. Retrieval and 6-category comparison of planned vs actual logistics data:
   - Pickup time variance
   - Delivery time variance
   - Shipment quantity variance (manifest vs POD received)
   - Transporter assignment comparison (booked vs executing)
   - POD completeness validation (signature, photos, recipient)
   - Freight charge discrepancy (agreed rate vs billed rate)
2. Discrepancy assignment, investigation, and resolution workflow
3. Reconciliation closure without silently changing original commitments
4. Export and REST API integrity
"""
import uuid
import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.api.deps import get_db
from app.core.config import settings
from app.main import app
from app.models.shipment import Shipment, ShipmentEvent, TransporterBooking, PickupCommitment, ShipmentAssignment
from app.models.transporter import Transporter
from app.models.operations import (
    ReconciliationRecord,
    LogisticsReconciliationItem,
    ProofOfDelivery,
    DeliveryDiscrepancy
)
from app.models.enums import (
    ShipmentStatus,
    BookingStatus,
    ReconciliationStatus,
    ReconciliationCategory,
    DiscrepancyItemStatus,
    PODVerificationStatus
)
from app.services.reconciliation_service import ReconciliationService


@pytest_asyncio.fixture
async def test_engine():
    engine = create_async_engine(
        settings.DATABASE_URL,
        poolclass=NullPool,
        connect_args={"ssl": False},
        echo=False,
    )
    yield engine
    await engine.dispose()


async def setup_test_org_and_client(test_engine, prefix="reconcil"):
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

    suffix = uuid.uuid4().hex[:6]
    email = f"{prefix}_{suffix}@example.com"
    reg_payload = {
        "full_name": "Reconciliation Officer",
        "email": email,
        "password": "SecurePassword123!",
        "confirm_password": "SecurePassword123!",
        "organization_name": f"Acme Audit Corp {suffix}",
        "org_type": "MANUFACTURER",
        "accept_terms": True,
    }
    reg_res = await client.post("/api/v1/auth/register", json=reg_payload)
    assert reg_res.status_code == 201, reg_res.text
    token = reg_res.json()["access_token"]
    user_id = reg_res.json()["user"]["id"]
    org_id = reg_res.json()["user"]["organization_id"]
    headers = {"Authorization": f"Bearer {token}"}

    return client, headers, uuid.UUID(org_id), uuid.UUID(user_id), session_factory


@pytest.mark.asyncio
async def test_reconciliation_comparison_engine_all_categories(test_engine):
    """
    Test planned vs. actual comparison across all 6 logistics categories.
    Verifies that original commitments remain completely intact.
    """
    client, headers, org_id, user_id, session_factory = await setup_test_org_and_client(test_engine, "eval")

    async with session_factory() as session:
        # Create 2 transporters (planned vs replacement)
        t_planned = Transporter(
            id=uuid.uuid4(),
            organization_id=org_id,
            name="Planned Express Logistics",
            code=f"PLN-{uuid.uuid4().hex[:4].upper()}",
            contact_person="Sam Planned",
            phone="+919111111111",
            email="planned@test.com",
            is_active=True
        )
        t_actual = Transporter(
            id=uuid.uuid4(),
            organization_id=org_id,
            name="Actual Carrier Replacement",
            code=f"ACT-{uuid.uuid4().hex[:4].upper()}",
            contact_person="Bob Actual",
            phone="+919222222222",
            email="actual@test.com",
            is_active=True
        )
        session.add_all([t_planned, t_actual])

        # Create Shipment with specific planned commitments
        scheduled_pickup = datetime.now(timezone.utc) - timedelta(hours=5)
        actual_pickup = datetime.now(timezone.utc) - timedelta(hours=3) # Delayed by 120 mins
        expected_delivery = datetime.now(timezone.utc) - timedelta(hours=1)
        actual_delivery = datetime.now(timezone.utc) # Delayed by 60 mins

        original_expected_qty = 100
        actual_received_qty = 95 # Shortage of 5 units

        shipment = Shipment(
            id=uuid.uuid4(),
            organization_id=org_id,
            tracking_number=f"TRK-REC-{uuid.uuid4().hex[:6].upper()}",
            status=ShipmentStatus.DELIVERED,
            origin_name="Bangalore Warehouse",
            origin_city="Bangalore",
            origin_address="Electronic City Phase 1",
            origin_state="Karnataka",
            origin_postal_code="560100",
            origin_contact_name="Bangalore Dispatch",
            origin_contact_phone="+919876543100",
            destination_name="Chennai DC",
            destination_city="Chennai",
            destination_address="Guindy Industrial Estate",
            destination_state="Tamil Nadu",
            destination_postal_code="600032",
            destination_contact_name="Chennai Receiver",
            destination_contact_phone="+919876543101",
            scheduled_pickup_time=scheduled_pickup,
            actual_pickup_time=actual_pickup,
            expected_delivery_time=expected_delivery,
            actual_delivery_time=actual_delivery,
            total_weight_kg=2500.0,
            package_count=original_expected_qty,
            goods_description="Precision Instruments"
        )
        session.add(shipment)

        # 1. Original booking with Planned Express
        booking1 = TransporterBooking(
            id=uuid.uuid4(),
            organization_id=org_id,
            shipment_id=shipment.id,
            transporter_id=t_planned.id,
            status=BookingStatus.REJECTED,
            agreed_rate=1500.0,
            expires_at=datetime.now(timezone.utc) + timedelta(days=1)
        )
        # 2. Confirmed booking with Actual Carrier (Overcharge scenario: agreed 1600.0)
        booking2 = TransporterBooking(
            id=uuid.uuid4(),
            organization_id=org_id,
            shipment_id=shipment.id,
            transporter_id=t_actual.id,
            status=BookingStatus.CONFIRMED,
            agreed_rate=1600.0,
            expires_at=datetime.now(timezone.utc) + timedelta(days=1)
        )
        session.add_all([booking1, booking2])

        # Incomplete POD (missing signature)
        pod = ProofOfDelivery(
            id=uuid.uuid4(),
            organization_id=org_id,
            shipment_id=shipment.id,
            signed_at=actual_delivery,
            signed_by_name="Kumar Receiver",
            expected_quantity=original_expected_qty,
            received_quantity=actual_received_qty,
            signature_image_url=None, # Missing signature!
            delivery_photo_urls=["s3://cargo/pod/photo1.jpg"],
            verification_status=PODVerificationStatus.REJECTED
        )
        session.add(pod)
        await session.commit()

        # Run comparison engine
        rec, items = await ReconciliationService.reconcile_shipment(
            session=session,
            shipment_id=shipment.id,
            organization_id=org_id,
            trigger_user_id=user_id
        )

        assert rec.status == ReconciliationStatus.DISCREPANCY
        assert rec.total_discrepancies > 0
        assert rec.has_mismatches is True
        assert len(items) == 6

        # Check Category 1: Pickup Time
        pickup_item = next(it for it in items if it.category == ReconciliationCategory.PICKUP_TIME.value)
        assert pickup_item.is_matched is False
        assert "Delayed" in pickup_item.discrepancy_delta

        # Check Category 2: Delivery Time
        delivery_item = next(it for it in items if it.category == ReconciliationCategory.DELIVERY_TIME.value)
        assert delivery_item.is_matched is False
        assert "Delayed delivery" in delivery_item.discrepancy_delta

        # Check Category 3: Quantity
        qty_item = next(it for it in items if it.category == ReconciliationCategory.SHIPMENT_QUANTITY.value)
        assert qty_item.is_matched is False
        assert "Shortage of 5 packages" in qty_item.discrepancy_delta

        # Check Category 4: Carrier Reassignment
        carrier_item = next(it for it in items if it.category == ReconciliationCategory.BOOKING_VS_ACTUAL_TRANSPORTER.value)
        assert carrier_item.is_matched is False
        assert "Transporter Reassigned" in carrier_item.discrepancy_delta

        # Check Category 5: POD Completeness
        pod_item = next(it for it in items if it.category == ReconciliationCategory.POD_COMPLETENESS.value)
        assert pod_item.is_matched is False
        assert "Incomplete POD" in pod_item.discrepancy_delta

        # Check Category 6: Freight charges
        charges_item = next(it for it in items if it.category == ReconciliationCategory.FREIGHT_CHARGES.value)
        assert charges_item.is_matched is True or charges_item.discrepancy_delta is not None

        # Verify original shipment commitment values are 100% PRESERVED
        await session.refresh(shipment)
        assert shipment.scheduled_pickup_time == scheduled_pickup
        assert shipment.expected_delivery_time == expected_delivery
        assert shipment.package_count == original_expected_qty


@pytest.mark.asyncio
async def test_reconciliation_item_investigation_and_closure(test_engine):
    """
    Test assigning discrepancy owners, recording investigation findings,
    resolving discrepancies, and closing the reconciliation record.
    """
    client, headers, org_id, user_id, session_factory = await setup_test_org_and_client(test_engine, "flow")

    async with session_factory() as session:
        t = Transporter(
            id=uuid.uuid4(),
            organization_id=org_id,
            name="Swift Carriers",
            code=f"SWF-{uuid.uuid4().hex[:4].upper()}",
            phone="+919888888888",
            is_active=True
        )
        session.add(t)

        now = datetime.now(timezone.utc)
        shipment = Shipment(
            id=uuid.uuid4(),
            organization_id=org_id,
            tracking_number=f"TRK-FLOW-{uuid.uuid4().hex[:6].upper()}",
            status=ShipmentStatus.DELIVERED,
            origin_name="Orig",
            origin_city="Pune",
            origin_address="Add 1",
            origin_state="MH",
            origin_postal_code="411001",
            origin_contact_name="Contact 1",
            origin_contact_phone="+919000000000",
            destination_name="Dest",
            destination_city="Mumbai",
            destination_address="Add 2",
            destination_state="MH",
            destination_postal_code="400001",
            destination_contact_name="Contact 2",
            destination_contact_phone="+919000000001",
            scheduled_pickup_time=now - timedelta(hours=3),
            actual_pickup_time=now - timedelta(hours=3), # Matched
            expected_delivery_time=now - timedelta(hours=1),
            actual_delivery_time=now - timedelta(hours=1), # Matched
            total_weight_kg=1000.0,
            package_count=50,
            goods_description="Parts"
        )
        session.add(shipment)

        booking = TransporterBooking(
            id=uuid.uuid4(),
            organization_id=org_id,
            shipment_id=shipment.id,
            transporter_id=t.id,
            status=BookingStatus.CONFIRMED,
            agreed_rate=1200.0,
            expires_at=now + timedelta(days=1)
        )
        session.add(booking)

        # POD with shortage of 1 unit
        pod = ProofOfDelivery(
            id=uuid.uuid4(),
            organization_id=org_id,
            shipment_id=shipment.id,
            signed_at=now - timedelta(hours=1),
            signed_by_name="Manager Dave",
            expected_quantity=50,
            received_quantity=49, # 1 unit shortage
            signature_image_url="s3://signature.png",
            delivery_photo_urls=["s3://photo.jpg"]
        )
        session.add(pod)
        await session.commit()

        # Reconcile
        rec, items = await ReconciliationService.reconcile_shipment(session, shipment.id, org_id, user_id)
        qty_item = next(it for it in items if it.category == ReconciliationCategory.SHIPMENT_QUANTITY.value)
        assert qty_item.status == "OPEN"

        # 1. Update Discrepancy item: Investigate & Resolve
        updated_item = await ReconciliationService.update_discrepancy_item(
            session=session,
            item_id=qty_item.id,
            organization_id=org_id,
            user_id=user_id,
            assigned_user_id=user_id,
            investigation_notes="Checked with warehouse dock; 1 unit left in staging",
            resolution_notes="Dock acknowledged missing piece was staged separately. No transporter penalty required.",
            status="RESOLVED"
        )
        assert updated_item.status == "RESOLVED"
        assert updated_item.assigned_user_id == user_id
        assert updated_item.resolution_notes is not None

        # 2. Close Reconciliation
        closed_rec = await ReconciliationService.close_reconciliation(
            session=session,
            shipment_id=shipment.id,
            organization_id=org_id,
            user_id=user_id,
            closure_notes="All discrepancies accounted for and verified by inventory manager."
        )
        assert closed_rec.status == ReconciliationStatus.CLOSED
        assert closed_rec.closed_by_user_id == user_id


@pytest.mark.asyncio
async def test_reconciliation_api_endpoints_and_csv_export(test_engine):
    """
    Test GET /api/v1/reconciliation, GET /api/v1/reconciliation/{id},
    and CSV export endpoint.
    """
    client, headers, org_id, user_id, session_factory = await setup_test_org_and_client(test_engine, "api")

    async with session_factory() as session:
        t = Transporter(
            id=uuid.uuid4(),
            organization_id=org_id,
            name="Globe Express",
            code=f"GLB-{uuid.uuid4().hex[:4].upper()}",
            phone="+919777777777",
            is_active=True
        )
        session.add(t)

        now = datetime.now(timezone.utc)
        shipment = Shipment(
            id=uuid.uuid4(),
            organization_id=org_id,
            tracking_number=f"TRK-API-{uuid.uuid4().hex[:6].upper()}",
            status=ShipmentStatus.DELIVERED,
            origin_name="Orig API",
            origin_city="Kolkata",
            origin_address="Salt Lake",
            origin_state="WB",
            origin_postal_code="700091",
            origin_contact_name="Contact API",
            origin_contact_phone="+919000000000",
            destination_name="Dest API",
            destination_city="Ranchi",
            destination_address="Main Road",
            destination_state="JH",
            destination_postal_code="834001",
            destination_contact_name="Contact API 2",
            destination_contact_phone="+919000000001",
            scheduled_pickup_time=now - timedelta(hours=4),
            actual_pickup_time=now - timedelta(hours=4),
            expected_delivery_time=now - timedelta(hours=1),
            actual_delivery_time=now - timedelta(hours=1),
            total_weight_kg=600.0,
            package_count=15,
            goods_description="Stationery"
        )
        session.add(shipment)
        await session.commit()

        # 1. Fetch detail endpoint (auto-triggers comparison)
        detail_res = await client.get(f"/api/v1/reconciliation/{shipment.id}", headers=headers)
        assert detail_res.status_code == 200
        data = detail_res.json()
        assert data["reconciliation"]["tracking_number"] == shipment.tracking_number
        assert len(data["items"]) == 6

        # 2. List reconciliations
        list_res = await client.get("/api/v1/reconciliation", headers=headers)
        assert list_res.status_code == 200
        assert len(list_res.json()) >= 1

        # 3. CSV export
        export_res = await client.get("/api/v1/reconciliation/export", headers=headers)
        assert export_res.status_code == 200
        assert "text/csv" in export_res.headers["content-type"]
        assert shipment.tracking_number in export_res.text
