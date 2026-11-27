"""
Tests for Phase 18: CargoPulse Analytics and Audit Trail
Validates:
1. Comprehensive logistics analytics calculated against known database fixtures:
   - Total shipments
   - Successful pickups & failed pickups
   - Pickup success rate (%)
   - On-time pickup rate (%)
   - On-time delivery rate (%)
   - Transporter acceptance rate (%)
   - Average pickup delay (minutes)
   - Average delivery delay (minutes)
   - Average recovery time (minutes)
   - Proof of Delivery (POD) completion rate (%)
   - Exception resolution time (minutes)
   - Cost per shipment calculation
   - Formal metric documentation dictionary
2. Transporter-level analytics and route-level reliability metrics:
   - Bookings tally (total, accepted, rejected, expired)
   - Transporter acceptance rate and on-time rate
   - Origin-destination corridor metrics and delay calculations
3. Audit Trail functionality:
   - Sanitization of sensitive keys (passwords, tokens, api keys, auth secrets)
   - Action recording, actor email preservation, correlation ID propagation
   - Strict tenant scoping (Org B cannot query Org A audit logs)
   - Immutability enforcement (PUT/PATCH/DELETE forbidden)
4. REST API integrity and CSV export generation:
   - Analytics overview, transporters, routes, dashboard bundle, and export CSV
   - Audit trail query, export CSV, and custom event logging
"""
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
    BookingStatus,
    CommitmentStatus,
    ExceptionSeverity,
    ExceptionStatus,
    ExceptionType,
    RecoveryStatus,
    RecoveryStrategy,
    ShipmentStatus,
)
from app.models.operations import ExceptionRecord, ProofOfDelivery, RecoveryCase
from app.models.shipment import (
    PickupCommitment,
    Shipment,
    ShipmentEvent,
    TransporterBooking,
)
from app.models.transporter import Transporter
from app.services.analytics_service import AnalyticsService
from app.services.audit_service import AuditService, sanitize_audit_data


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


async def setup_test_org_and_client(test_engine, prefix="analytics"):
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
        "full_name": "Analytics Director",
        "email": email,
        "password": "SecurePassword123!",
        "confirm_password": "SecurePassword123!",
        "organization_name": f"Analytics Test Corp {suffix}",
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
async def test_analytics_overview_calculation_against_fixtures(test_engine):
    """
    Validates calculation of all 13 core logistics metrics against precise known fixtures.
    """
    client, headers, org_id, user_id, session_factory = await setup_test_org_and_client(test_engine, "kpi")

    async with session_factory() as session:
        # Create Transporter
        transporter = Transporter(
            id=uuid.uuid4(),
            organization_id=org_id,
            name="Apex Fleet Logistics",
            code=f"APX-{uuid.uuid4().hex[:4].upper()}",
            contact_person="Jane Driver",
            phone="+919888888888",
            email="apex@fleet.com",
            is_active=True,
        )
        session.add(transporter)

        now = datetime.now(timezone.utc)
        base_time = now - timedelta(days=2)

        # 1. Shipment 1: Successful on-time pickup, on-time delivery, POD submitted, cost $1200
        s1 = Shipment(
            id=uuid.uuid4(),
            organization_id=org_id,
            tracking_number=f"TRK-S1-{uuid.uuid4().hex[:6].upper()}",
            status=ShipmentStatus.DELIVERED,
            origin_name="Mumbai Hub",
            origin_address="100 Port Rd",
            origin_city="Mumbai",
            origin_state="Maharashtra",
            origin_postal_code="400001",
            origin_contact_name="Bob M",
            origin_contact_phone="+919111111111",
            destination_name="Pune Center",
            destination_address="200 Tech St",
            destination_city="Pune",
            destination_state="Maharashtra",
            destination_postal_code="411001",
            destination_contact_name="Alice P",
            destination_contact_phone="+919222222222",
            scheduled_pickup_time=base_time,
            actual_pickup_time=base_time + timedelta(minutes=5),  # 5 min delta <= 15m -> On-Time
            expected_delivery_time=base_time + timedelta(hours=6),
            actual_delivery_time=base_time + timedelta(hours=6),  # Exactly on time
            total_weight_kg=Decimal("1500.00"),
            package_count=100,
            goods_description="Medical equipment",
            invoice_value=Decimal("1200.00"),
            created_at=base_time,
        )
        session.add(s1)

        # Booking for S1 (ACCEPTED)
        b1 = TransporterBooking(
            id=uuid.uuid4(),
            organization_id=org_id,
            shipment_id=s1.id,
            transporter_id=transporter.id,
            status=BookingStatus.ACCEPTED,
            agreed_rate=Decimal("1200.00"),
            expires_at=base_time + timedelta(hours=1),
            created_at=base_time,
        )
        session.add(b1)

        # POD for S1
        pod1 = ProofOfDelivery(
            id=uuid.uuid4(),
            organization_id=org_id,
            shipment_id=s1.id,
            signed_by_name="Alice P",
            received_quantity=100,
            signed_at=base_time + timedelta(hours=6),
            signature_image_url="https://s3.local/pod1.png",
            delivery_photo_urls=["https://s3.local/photo1.jpg"],
        )
        session.add(pod1)

        # 2. Shipment 2: Successful pickup with 30-min delay, delivered with 45-min delay, cost $1800
        s2 = Shipment(
            id=uuid.uuid4(),
            organization_id=org_id,
            tracking_number=f"TRK-S2-{uuid.uuid4().hex[:6].upper()}",
            status=ShipmentStatus.DELIVERED,
            origin_name="Mumbai Hub",
            origin_address="100 Port Rd",
            origin_city="Mumbai",
            origin_state="Maharashtra",
            origin_postal_code="400001",
            origin_contact_name="Bob M",
            origin_contact_phone="+919111111111",
            destination_name="Pune Center",
            destination_address="200 Tech St",
            destination_city="Pune",
            destination_state="Maharashtra",
            destination_postal_code="411001",
            destination_contact_name="Alice P",
            destination_contact_phone="+919222222222",
            scheduled_pickup_time=base_time,
            actual_pickup_time=base_time + timedelta(minutes=30),  # 30 min delay
            expected_delivery_time=base_time + timedelta(hours=6),
            actual_delivery_time=base_time + timedelta(hours=6, minutes=45),  # 45 min delay
            total_weight_kg=Decimal("2000.00"),
            package_count=150,
            goods_description="Industrial supplies",
            invoice_value=Decimal("1800.00"),
            created_at=base_time,
        )
        session.add(s2)

        # Booking for S2 (ACCEPTED)
        b2 = TransporterBooking(
            id=uuid.uuid4(),
            organization_id=org_id,
            shipment_id=s2.id,
            transporter_id=transporter.id,
            status=BookingStatus.ACCEPTED,
            agreed_rate=Decimal("1800.00"),
            expires_at=base_time + timedelta(hours=1),
            created_at=base_time,
        )
        session.add(b2)

        # 3. Shipment 3: Failed pickup (breached commitment, overdue exception)
        s3 = Shipment(
            id=uuid.uuid4(),
            organization_id=org_id,
            tracking_number=f"TRK-S3-{uuid.uuid4().hex[:6].upper()}",
            status=ShipmentStatus.EXCEPTION,
            origin_name="Mumbai Hub",
            origin_address="100 Port Rd",
            origin_city="Mumbai",
            origin_state="Maharashtra",
            origin_postal_code="400001",
            origin_contact_name="Bob M",
            origin_contact_phone="+919111111111",
            destination_name="Nashik Hub",
            destination_address="50 Highway Rd",
            destination_city="Nashik",
            destination_state="Maharashtra",
            destination_postal_code="422001",
            destination_contact_name="Carol N",
            destination_contact_phone="+919333333333",
            scheduled_pickup_time=base_time - timedelta(hours=2),
            expected_delivery_time=base_time + timedelta(hours=10),
            total_weight_kg=Decimal("1000.00"),
            package_count=50,
            goods_description="Chemical drums",
            created_at=base_time,
        )
        session.add(s3)

        c3 = PickupCommitment(
            id=uuid.uuid4(),
            organization_id=org_id,
            shipment_id=s3.id,
            transporter_id=transporter.id,
            status=CommitmentStatus.BREACHED,
            committed_pickup_slot_start=base_time - timedelta(hours=3),
            committed_pickup_slot_end=base_time - timedelta(hours=2),
            pickup_deadline=base_time - timedelta(hours=2),
        )
        session.add(c3)

        e3 = ExceptionRecord(
            id=uuid.uuid4(),
            organization_id=org_id,
            shipment_id=s3.id,
            exception_type=ExceptionType.PICKUP_OVERDUE,
            severity=ExceptionSeverity.CRITICAL,
            status=ExceptionStatus.RESOLVED,
            title="Pickup Overdue",
            description="Carrier failed to report arrival within window",
            reported_at=base_time,
            resolved_at=base_time + timedelta(minutes=40),  # 40 min resolution time
            created_at=base_time,
        )
        session.add(e3)

        # Recovery Case for S3
        rc3 = RecoveryCase(
            id=uuid.uuid4(),
            organization_id=org_id,
            exception_id=e3.id,
            case_number=f"RC-{uuid.uuid4().hex[:6].upper()}",
            strategy=RecoveryStrategy.REASSIGN_TRANSPORTER,
            status=RecoveryStatus.COMPLETED,
            proposed_solution="Reassign load to alternative available fleet",
            resolved_at=base_time + timedelta(minutes=25),  # 25 min recovery time
            created_at=base_time,
        )
        session.add(rc3)

        # Additional Bookings: 1 REJECTED, 1 EXPIRED (for transporter acceptance test)
        b3 = TransporterBooking(
            id=uuid.uuid4(),
            organization_id=org_id,
            shipment_id=s3.id,
            transporter_id=transporter.id,
            status=BookingStatus.REJECTED,
            expires_at=base_time + timedelta(hours=1),
            created_at=base_time,
        )
        b4 = TransporterBooking(
            id=uuid.uuid4(),
            organization_id=org_id,
            shipment_id=s3.id,
            transporter_id=transporter.id,
            status=BookingStatus.EXPIRED,
            expires_at=base_time - timedelta(minutes=10),
            created_at=base_time,
        )
        session.add(b3)
        session.add(b4)

        # 4. Shipment 4: Draft (future pickup, no attempt yet)
        s4 = Shipment(
            id=uuid.uuid4(),
            organization_id=org_id,
            tracking_number=f"TRK-S4-{uuid.uuid4().hex[:6].upper()}",
            status=ShipmentStatus.DRAFT,
            origin_name="Mumbai Hub",
            origin_address="100 Port Rd",
            origin_city="Mumbai",
            origin_state="Maharashtra",
            origin_postal_code="400001",
            origin_contact_name="Bob M",
            origin_contact_phone="+919111111111",
            destination_name="Pune Center",
            destination_address="200 Tech St",
            destination_city="Pune",
            destination_state="Maharashtra",
            destination_postal_code="411001",
            destination_contact_name="Alice P",
            destination_contact_phone="+919222222222",
            scheduled_pickup_time=now + timedelta(days=2),
            expected_delivery_time=now + timedelta(days=3),
            total_weight_kg=Decimal("500.00"),
            package_count=20,
            goods_description="Retail parcels",
            created_at=now,
        )
        session.add(s4)

        await session.commit()

        # Run calculation
        metrics = await AnalyticsService.get_overview_metrics(
            session=session,
            organization_id=org_id,
        )

        # Assertions
        assert metrics.total_shipments == 4
        assert metrics.successful_pickups == 2  # s1 and s2
        assert metrics.failed_pickups == 1      # s3
        # Pickup success rate: 2 / (2 + 1) * 100 = 66.67%
        assert metrics.pickup_success_rate == 66.67
        # On-time pickup rate: 1 on-time (s1) out of 2 successful = 50.0%
        assert metrics.on_time_pickup_rate == 50.0
        # On-time delivery rate: 1 on-time (s1) out of 2 delivered (s1, s2) = 50.0%
        assert metrics.on_time_delivery_rate == 50.0
        # Transporter acceptance: 2 accepted out of 4 decided (b1, b2 vs b1, b2, b3, b4) = 50.0%
        assert metrics.transporter_acceptance_rate == 50.0
        # Average pickup delay: 30.0 min (s2)
        assert metrics.average_pickup_delay_minutes == 30.0
        # Average delivery delay: 45.0 min (s2)
        assert metrics.average_delivery_delay_minutes == 45.0
        # Average recovery time: 25.0 min (rc3)
        assert metrics.average_recovery_time_minutes == 25.0
        # POD completion rate: 1 POD out of 2 delivered = 50.0%
        assert metrics.pod_completion_rate == 50.0
        # Exception resolution time: 40.0 min (e3)
        assert metrics.exception_resolution_time_minutes == 40.0
        # Cost per shipment: ($1200 + $1800) / 2 = $1500.00
        assert metrics.cost_per_shipment == 1500.0
        assert metrics.total_cost == 3000.0
        assert metrics.cost_shipment_count == 2
        # Ensure definitions dictionary is populated
        assert "total_shipments" in metrics.metric_definitions
        assert "cost_per_shipment" in metrics.metric_definitions


@pytest.mark.asyncio
async def test_transporter_and_route_metrics(test_engine):
    """
    Validates transporter-specific rankings and route corridor reliability metrics.
    """
    client, headers, org_id, user_id, session_factory = await setup_test_org_and_client(test_engine, "routes")

    async with session_factory() as session:
        t = Transporter(
            id=uuid.uuid4(),
            organization_id=org_id,
            name="Western Express",
            code=f"WEX-{uuid.uuid4().hex[:4].upper()}",
            contact_person="Raj Patel",
            phone="+919777777777",
            email="raj@westernexpress.in",
            is_active=True,
        )
        session.add(t)

        now = datetime.now(timezone.utc)
        s = Shipment(
            id=uuid.uuid4(),
            organization_id=org_id,
            tracking_number=f"TRK-WEX-{uuid.uuid4().hex[:6].upper()}",
            status=ShipmentStatus.DELIVERED,
            origin_name="Ahmedabad Plant",
            origin_address="GIDC 1",
            origin_city="Ahmedabad",
            origin_state="Gujarat",
            origin_postal_code="380001",
            origin_contact_name="Dinesh",
            origin_contact_phone="+919444444444",
            destination_name="Surat Hub",
            destination_address="Ring Rd",
            destination_city="Surat",
            destination_state="Gujarat",
            destination_postal_code="395001",
            destination_contact_name="Bhavin",
            destination_contact_phone="+919555555555",
            scheduled_pickup_time=now - timedelta(days=1),
            actual_pickup_time=now - timedelta(days=1),
            expected_delivery_time=now - timedelta(hours=18),
            actual_delivery_time=now - timedelta(hours=18),
            total_weight_kg=Decimal("3000.00"),
            package_count=80,
            goods_description="Textiles",
            created_at=now - timedelta(days=1),
        )
        session.add(s)

        b = TransporterBooking(
            id=uuid.uuid4(),
            organization_id=org_id,
            shipment_id=s.id,
            transporter_id=t.id,
            status=BookingStatus.ACCEPTED,
            expires_at=now,
            created_at=now - timedelta(days=1),
        )
        session.add(b)
        await session.commit()

        # 1. Transporter Metrics
        t_metrics = await AnalyticsService.get_transporter_metrics(
            session=session,
            organization_id=org_id,
            transporter_id=t.id,
        )
        assert len(t_metrics) == 1
        t_res = t_metrics[0]
        assert t_res.transporter_id == t.id
        assert t_res.total_bookings == 1
        assert t_res.accepted_bookings == 1
        assert t_res.acceptance_rate == 100.0
        assert t_res.successful_pickups == 1
        assert t_res.on_time_deliveries == 1
        assert t_res.on_time_delivery_rate == 100.0
        assert len(t_res.performance_trend) >= 1

        # 2. Route Metrics
        route_metrics = await AnalyticsService.get_route_reliability_metrics(
            session=session,
            organization_id=org_id,
        )
        assert any(r.lane_name == "Ahmedabad -> Surat" for r in route_metrics)
        lane = next(r for r in route_metrics if r.lane_name == "Ahmedabad -> Surat")
        assert lane.total_shipments == 1
        assert lane.pickup_success_rate == 100.0
        assert lane.on_time_delivery_rate == 100.0


@pytest.mark.asyncio
async def test_audit_service_recording_sanitization_and_isolation(test_engine):
    """
    Validates audit trail logging, sensitive credential masking, filtering, and strict tenant isolation.
    """
    client, headers, org_a_id, user_a_id, session_factory = await setup_test_org_and_client(test_engine, "audita")
    _, _, org_b_id, _, _ = await setup_test_org_and_client(test_engine, "auditb")

    async with session_factory() as session:
        # 1. Log event with sensitive credentials
        resource_id = uuid.uuid4()
        cid = f"req-{uuid.uuid4().hex[:8]}"

        raw_changes = {
            "password": "CleartextPassword999!",
            "secret_token": "jwt_live_token_abc",
            "api_key": "sk_test_12345678",
            "authorization_header": "Bearer tokenXYZ",
            "carrier_code": "APX",
            "nested": {
                "admin_password": "nested_secret_pass",
                "normal_param": "visible_value",
            },
        }

        entry = await AuditService.log_event(
            session=session,
            organization_id=org_a_id,
            action="USER_SECURITY_CHANGE",
            resource_type="User",
            resource_id=resource_id,
            user_id=user_a_id,
            actor_email="admin@acme.com",
            correlation_id=cid,
            before={"password": "old_password_1"},
            after=raw_changes,
            commit=True,
        )

        assert entry.id is not None
        assert entry.organization_id == org_a_id
        assert entry.action == "USER_SECURITY_CHANGE"
        assert entry.actor_email == "admin@acme.com"
        assert entry.correlation_id == cid

        # Verify sensitive secret sanitization
        after_changes = entry.changes.get("after", {})
        assert after_changes["password"] == "[REDACTED]"
        assert after_changes["secret_token"] == "[REDACTED]"
        assert after_changes["api_key"] == "[REDACTED]"
        assert after_changes["authorization_header"] == "[REDACTED]"
        assert after_changes["carrier_code"] == "APX"
        assert after_changes["nested"]["admin_password"] == "[REDACTED]"
        assert after_changes["nested"]["normal_param"] == "visible_value"

        # 2. Query logs with filters
        logs, total = await AuditService.query_logs(
            session=session,
            organization_id=org_a_id,
            action="USER_SECURITY_CHANGE",
        )
        assert total >= 1
        assert any(l.correlation_id == cid for l in logs)

        # 3. Strict Tenant Scoping: Org B must NOT see Org A's audit records
        b_logs, b_total = await AuditService.query_logs(
            session=session,
            organization_id=org_b_id,
            action="USER_SECURITY_CHANGE",
        )
        assert b_total == 0
        assert not any(l.id == entry.id for l in b_logs)

        # 4. CSV export validation
        csv_text = await AuditService.export_logs_csv(
            session=session,
            organization_id=org_a_id,
        )
        assert "Timestamp (UTC)" in csv_text
        assert "USER_SECURITY_CHANGE" in csv_text
        assert "CleartextPassword999!" not in csv_text  # Secrets must NEVER leak in export!


@pytest.mark.asyncio
async def test_analytics_and_audit_api_endpoints_and_csv_export(test_engine):
    """
    Validates REST API endpoints for Analytics and Audit Trail, plus immutability enforcement.
    """
    client, headers, org_id, user_id, session_factory = await setup_test_org_and_client(test_engine, "restapi")

    # 1. GET /api/v1/analytics/overview
    res_overview = await client.get("/api/v1/analytics/overview", headers=headers)
    assert res_overview.status_code == 200, res_overview.text
    data_overview = res_overview.json()
    assert "total_shipments" in data_overview
    assert "pickup_success_rate" in data_overview
    assert "metric_definitions" in data_overview

    # 2. GET /api/v1/analytics/transporters
    res_trans = await client.get("/api/v1/analytics/transporters", headers=headers)
    assert res_trans.status_code == 200, res_trans.text
    assert isinstance(res_trans.json(), list)

    # 3. GET /api/v1/analytics/routes
    res_routes = await client.get("/api/v1/analytics/routes", headers=headers)
    assert res_routes.status_code == 200, res_routes.text
    assert isinstance(res_routes.json(), list)

    # 4. GET /api/v1/analytics/dashboard
    res_dash = await client.get("/api/v1/analytics/dashboard", headers=headers)
    assert res_dash.status_code == 200, res_dash.text
    assert "overview" in res_dash.json()
    assert "transporters" in res_dash.json()
    assert "routes" in res_dash.json()

    # 5. GET /api/v1/analytics/export (CSV)
    res_csv = await client.get("/api/v1/analytics/export", headers=headers)
    assert res_csv.status_code == 200, res_csv.text
    assert res_csv.headers["content-type"].startswith("text/csv")
    assert "CARGOPULSE LOGISTICS ANALYTICS OVERVIEW" in res_csv.text

    # 6. POST /api/v1/audit/events (Explicit audit logging)
    audit_payload = {
        "action": "ROLE_PERMISSION_CHANGED",
        "resource_type": "RolePermission",
        "resource_id": str(uuid.uuid4()),
        "correlation_id": "corr-test-1234",
        "before": {"role": "DISPATCHER", "permission": "READ"},
        "after": {"role": "DISPATCHER", "permission": "WRITE"},
        "metadata": {"reason": "Elevation approved by security director"},
    }
    res_post_audit = await client.post("/api/v1/audit/events", json=audit_payload, headers=headers)
    assert res_post_audit.status_code == 201, res_post_audit.text
    audit_id = res_post_audit.json()["id"]

    # 7. GET /api/v1/audit/logs
    res_logs = await client.get("/api/v1/audit/logs", headers=headers)
    assert res_logs.status_code == 200, res_logs.text
    assert res_logs.json()["total"] >= 1
    items = res_logs.json()["items"]
    assert any(i["id"] == audit_id for i in items)

    # 8. GET /api/v1/audit/export (CSV)
    res_audit_csv = await client.get("/api/v1/audit/export", headers=headers)
    assert res_audit_csv.status_code == 200, res_audit_csv.text
    assert res_audit_csv.headers["content-type"].startswith("text/csv")
    assert "ROLE_PERMISSION_CHANGED" in res_audit_csv.text

    # 9. Immutability: Verify PUT/PATCH/DELETE on audit logs are strictly forbidden (403)
    res_put = await client.put(f"/api/v1/audit/logs/{audit_id}", headers=headers, json={"action": "TAMPERED"})
    assert res_put.status_code == 403
    res_del = await client.delete(f"/api/v1/audit/logs/{audit_id}", headers=headers)
    assert res_del.status_code == 403
