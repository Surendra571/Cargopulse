"""
Tests for Phase 16: CargoPulse AI Logistics Coordinator
Tests the 10 backend tools, tenant isolation, natural language question routing,
and human-in-the-loop action proposals, approvals, and rejections.
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
from app.models.shipment import Shipment, ShipmentEvent, TransporterBooking
from app.models.transporter import Transporter, Vehicle, Driver
from app.models.operations import ExceptionRecord
from app.models.integrations import AIActionRecord
from app.models.enums import (
    ShipmentStatus,
    ExceptionStatus,
    ExceptionSeverity,
    ExceptionPriority,
    ExceptionType,
    BookingStatus
)
from app.services.ai import tools
from app.services.ai.coordinator_service import AICoordinatorService


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


async def setup_test_org_and_client(test_engine, prefix="ai_test"):
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
        "full_name": "AI Ops Coordinator",
        "email": email,
        "password": "SecurePassword123!",
        "confirm_password": "SecurePassword123!",
        "organization_name": f"Acme AI Logistics {suffix}",
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
async def test_ai_tools_direct_execution(test_engine):
    """
    Test direct execution of backend AI tools with database validation and tenant isolation.
    """
    client, headers, org_id, user_id, session_factory = await setup_test_org_and_client(test_engine, "tools")

    async with session_factory() as db_session:
        # Create a test transporter
        transporter = Transporter(
            id=uuid.uuid4(),
            organization_id=org_id,
            name="Apex Express AI Test",
            code=f"APX-{uuid.uuid4().hex[:4].upper()}",
            contact_person="Alex Agent",
            phone="+919876543210",
            email="apex@test.com",
            is_active=True,
            reliability_score=94.0,
            total_deliveries=100,
            on_time_deliveries=96
        )
        db_session.add(transporter)

        # Create an overdue shipment
        past_time = datetime.now(timezone.utc) - timedelta(hours=2)
        delivery_time = datetime.now(timezone.utc) + timedelta(days=2)
        shipment = Shipment(
            id=uuid.uuid4(),
            organization_id=org_id,
            tracking_number=f"TRK-AI-{uuid.uuid4().hex[:6].upper()}",
            status=ShipmentStatus.COMMITTED,
            origin_name="Mumbai Hub",
            origin_city="Mumbai",
            origin_address="Plot 10, Logistics Park",
            origin_state="Maharashtra",
            origin_postal_code="400001",
            origin_contact_name="Origin Contact",
            origin_contact_phone="+919876543201",
            destination_name="Pune Center",
            destination_city="Pune",
            destination_address="Sector 4, MIDC",
            destination_state="Maharashtra",
            destination_postal_code="411001",
            destination_contact_name="Dest Contact",
            destination_contact_phone="+919876543202",
            scheduled_pickup_time=past_time,
            expected_delivery_time=delivery_time,
            total_weight_kg=1200.0,
            package_count=40,
            goods_description="Electronics Batch"
        )
        db_session.add(shipment)

        # Create booking for transporter
        booking = TransporterBooking(
            id=uuid.uuid4(),
            organization_id=org_id,
            shipment_id=shipment.id,
            transporter_id=transporter.id,
            status=BookingStatus.CONFIRMED,
            expires_at=delivery_time
        )
        db_session.add(booking)

        # Create an active exception
        exception = ExceptionRecord(
            id=uuid.uuid4(),
            organization_id=org_id,
            shipment_id=shipment.id,
            title="Pickup Overdue Exception",
            exception_type=ExceptionType.PICKUP_OVERDUE,
            severity=ExceptionSeverity.CRITICAL,
            priority=ExceptionPriority.HIGH,
            status=ExceptionStatus.OPEN,
            description="Transporter vehicle failed to arrive within deadline."
        )
        db_session.add(exception)

        await db_session.commit()

        # Tool 1: get_shipment_details
        details = await tools.get_shipment_details(db_session, org_id, shipment.tracking_number)
        assert details["found"] is True
        assert details["tracking_number"] == shipment.tracking_number
        assert details["is_pickup_overdue"] is True
        assert details["assigned_transporter_name"] == "Apex Express AI Test"

        # Cross-tenant isolation check: foreign org shouldn't see it
        foreign_org_id = uuid.uuid4()
        foreign_details = await tools.get_shipment_details(db_session, foreign_org_id, shipment.tracking_number)
        assert foreign_details["found"] is False

        # Tool 2: get_shipment_timeline
        timeline = await tools.get_shipment_timeline(db_session, org_id, str(shipment.id))
        assert timeline["found"] is True

        # Tool 3: list_overdue_pickups
        overdue = await tools.list_overdue_pickups(db_session, org_id, limit=10)
        assert overdue["count"] >= 1
        assert any(s["shipment_id"] == str(shipment.id) for s in overdue["overdue_shipments"])

        # Tool 4: get_open_exceptions
        exceptions_res = await tools.get_open_exceptions(db_session, org_id, severity="CRITICAL")
        assert exceptions_res["count"] >= 1
        assert any(e["id"] == str(exception.id) for e in exceptions_res["exceptions"])

        # Tool 5: get_transporter_performance
        perf = await tools.get_transporter_performance(db_session, org_id, str(transporter.id))
        assert perf["found"] is True
        assert perf["name"] == "Apex Express AI Test"
        assert perf["pickup_reliability_score"] == 0.94

        # Tool 6: find_eligible_transporters
        eligible = await tools.find_eligible_transporters(db_session, org_id, str(shipment.id))
        assert eligible["found"] is True

        # Tool 7: create_recovery_recommendation
        rec = await tools.create_recovery_recommendation(db_session, org_id, str(shipment.id), "Driver breakdown")
        assert rec["success"] is True
        assert rec["recommended_action"] == "REASSIGN_TRANSPORTER"

        # Tool 8: request_reassignment_approval
        prop = await tools.request_reassignment_approval(
            session=db_session,
            organization_id=org_id,
            shipment_id=str(shipment.id),
            replacement_transporter_id=str(transporter.id),
            reason="Vehicle breakdown recovery",
            additional_cost=75.0,
            user_id=user_id
        )
        assert prop["success"] is True
        assert prop["status"] == "PENDING"
        assert prop["requires_approval"] is True

        # Tool 9: get_delivery_status
        deliv = await tools.get_delivery_status(db_session, org_id, str(shipment.id))
        assert deliv["found"] is True
        assert deliv["is_delivered"] is False

        # Tool 10: summarize_reconciliation
        recon = await tools.summarize_reconciliation(db_session, org_id, str(shipment.id))
        assert recon["found"] is True


@pytest.mark.asyncio
async def test_ai_coordinator_approval_and_rejection_workflows(test_engine):
    """
    Test human-in-the-loop approval execution and rejection safeguards.
    """
    client, headers, org_id, user_id, session_factory = await setup_test_org_and_client(test_engine, "appr")

    async with session_factory() as db_session:
        # Create 2 transporters
        t1 = Transporter(
            id=uuid.uuid4(),
            organization_id=org_id,
            name="Carrier One",
            code=f"C1-{uuid.uuid4().hex[:4].upper()}",
            contact_person="C1",
            phone="+919000000001",
            email="c1@test.com",
            is_active=True
        )
        t2 = Transporter(
            id=uuid.uuid4(),
            organization_id=org_id,
            name="Carrier Two",
            code=f"C2-{uuid.uuid4().hex[:4].upper()}",
            contact_person="C2",
            phone="+919000000002",
            email="c2@test.com",
            is_active=True
        )
        db_session.add_all([t1, t2])

        past_time = datetime.now(timezone.utc) - timedelta(hours=1)
        delivery_time = datetime.now(timezone.utc) + timedelta(days=2)
        shipment = Shipment(
            id=uuid.uuid4(),
            organization_id=org_id,
            tracking_number=f"TRK-APPR-{uuid.uuid4().hex[:6].upper()}",
            status=ShipmentStatus.COMMITTED,
            origin_name="Hub A",
            origin_city="Delhi",
            origin_address="Delhi Gate",
            origin_state="Delhi",
            origin_postal_code="110001",
            origin_contact_name="Origin Contact",
            origin_contact_phone="+919876543201",
            destination_name="Hub B",
            destination_city="Jaipur",
            destination_address="Tonk Road",
            destination_state="Rajasthan",
            destination_postal_code="302001",
            destination_contact_name="Dest Contact",
            destination_contact_phone="+919876543202",
            scheduled_pickup_time=past_time,
            expected_delivery_time=delivery_time,
            total_weight_kg=800.0,
            package_count=20,
            goods_description="Garments"
        )
        db_session.add(shipment)

        booking1 = TransporterBooking(
            id=uuid.uuid4(),
            organization_id=org_id,
            shipment_id=shipment.id,
            transporter_id=t1.id,
            status=BookingStatus.CONFIRMED,
            expires_at=delivery_time
        )
        db_session.add(booking1)
        await db_session.commit()

        # Create Reassignment Proposal 1 (To be approved)
        prop1 = await tools.request_reassignment_approval(
            session=db_session,
            organization_id=org_id,
            shipment_id=str(shipment.id),
            replacement_transporter_id=str(t2.id),
            reason="Test approval execution",
            additional_cost=40.0,
            user_id=user_id
        )
        action1_id = uuid.UUID(prop1["action_id"])

        # Approve action 1
        appr_res = await AICoordinatorService.approve_action(
            session=db_session,
            action_id=action1_id,
            user_id=user_id,
            organization_id=org_id,
            approval_notes="Approved for express delivery"
        )
        assert appr_res["success"] is True
        assert appr_res["status"] == "EXECUTED"

        # Verify shipment assignment updated to Carrier Two
        b2_res = await db_session.execute(
            select(TransporterBooking).where(
                TransporterBooking.shipment_id == shipment.id,
                TransporterBooking.transporter_id == t2.id
            )
        )
        b2 = b2_res.scalar_one_or_none()
        assert b2 is not None

        # Verify idempotency
        appr_again = await AICoordinatorService.approve_action(
            session=db_session,
            action_id=action1_id,
            user_id=user_id,
            organization_id=org_id
        )
        assert appr_again["success"] is True
        assert "already executed" in appr_again["message"]

        # Create Reassignment Proposal 2 (To be rejected)
        prop2 = await tools.request_reassignment_approval(
            session=db_session,
            organization_id=org_id,
            shipment_id=str(shipment.id),
            replacement_transporter_id=str(t1.id),
            reason="Test rejection",
            additional_cost=100.0,
            user_id=user_id
        )
        action2_id = uuid.UUID(prop2["action_id"])

        # Reject action 2
        rej_res = await AICoordinatorService.reject_action(
            session=db_session,
            action_id=action2_id,
            user_id=user_id,
            organization_id=org_id,
            rejection_reason="Excessive additional cost"
        )
        assert rej_res["success"] is True
        assert rej_res["status"] == "REJECTED"

        # Attempting to approve rejected action must fail
        fail_appr = await AICoordinatorService.approve_action(
            session=db_session,
            action_id=action2_id,
            user_id=user_id,
            organization_id=org_id
        )
        assert fail_appr["success"] is False
        assert "Cannot approve a previously rejected action" in fail_appr["error"]


@pytest.mark.asyncio
async def test_ai_coordinator_conversations_and_chat_api(test_engine):
    """
    Test full REST API workflow for AI conversations and questions.
    """
    client, headers, org_id, user_id, session_factory = await setup_test_org_and_client(test_engine, "chat")

    # 1. Create conversation
    res = await client.post(
        "/api/v1/ai-coordinator/conversations",
        headers=headers,
        json={"title": "Test AI Chat Session"}
    )
    assert res.status_code == 201
    conv_data = res.json()
    conv_id = conv_data["id"]
    assert conv_data["title"] == "Test AI Chat Session"

    # 2. List conversations
    res = await client.get("/api/v1/ai-coordinator/conversations", headers=headers)
    assert res.status_code == 200
    assert any(c["id"] == conv_id for c in res.json())

    # 3. Ask question: "Which shipments have missed pickup deadlines?"
    chat_res = await client.post(
        f"/api/v1/ai-coordinator/conversations/{conv_id}/messages",
        headers=headers,
        json={"content": "Which shipments have missed pickup deadlines?"}
    )
    assert chat_res.status_code == 200
    chat_data = chat_res.json()
    assert chat_data["user_message"]["content"] == "Which shipments have missed pickup deadlines?"
    assert chat_data["assistant_message"]["sender_type"] == "assistant"
    assert len(chat_data["assistant_message"]["tool_calls"]) > 0
    assert any(t["tool_name"] == "list_overdue_pickups" for t in chat_data["assistant_message"]["tool_calls"])

    # 4. Ask question: "Which exceptions are critical?"
    chat_res2 = await client.post(
        f"/api/v1/ai-coordinator/conversations/{conv_id}/messages",
        headers=headers,
        json={"content": "Which exceptions are critical?"}
    )
    assert chat_res2.status_code == 200
    chat_data2 = chat_res2.json()
    assert any(t["tool_name"] == "get_open_exceptions" for t in chat_data2["assistant_message"]["tool_calls"])

    # 5. Fetch full conversation detail
    detail_res = await client.get(
        f"/api/v1/ai-coordinator/conversations/{conv_id}",
        headers=headers
    )
    assert detail_res.status_code == 200
    detail_data = detail_res.json()
    assert len(detail_data["messages"]) >= 4
