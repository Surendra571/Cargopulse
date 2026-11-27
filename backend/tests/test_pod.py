import io
import uuid
from datetime import datetime, timedelta, timezone
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
    DiscrepancyType,
    ExceptionType,
    PODVerificationStatus,
    ShipmentStatus,
)
from app.models.operations import DeliveryDiscrepancy, ExceptionRecord, ProofOfDelivery
from app.models.shipment import Shipment


@pytest_asyncio.fixture
async def test_engine():
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool, connect_args={"ssl": False}, echo=False)
    yield engine
    await engine.dispose()


async def create_user_session(test_engine, prefix: str = "pod"):
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
        "full_name": "Delivery Operations Lead",
        "email": email,
        "password": "SecurePassword123!",
        "confirm_password": "SecurePassword123!",
        "organization_name": f"Acme Manufacturing {suffix}",
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

    return user_client, headers, token, org_id, user_id


async def _create_test_shipment(client: AsyncClient, headers: dict, package_count: int = 100) -> dict:
    pickup_time = datetime.now(timezone.utc) + timedelta(hours=2)
    delivery_time = datetime.now(timezone.utc) + timedelta(hours=26)
    payload = {
        "customer_name": "Apex Distribution Center",
        "customer_reference": f"PO-{uuid.uuid4().hex[:6].upper()}",
        "origin_name": "Detroit Plant 1",
        "origin_address": "1000 Assembly Way",
        "origin_city": "Detroit",
        "origin_state": "MI",
        "origin_postal_code": "48201",
        "origin_contact_name": "Dock Supervisor",
        "origin_contact_phone": "+1-313-555-0111",
        "destination_name": "Columbus Logistics Park",
        "destination_address": "2000 Fulfillment Blvd",
        "destination_city": "Columbus",
        "destination_state": "OH",
        "destination_postal_code": "43004",
        "destination_contact_name": "Receiving Manager",
        "destination_contact_phone": "+1-614-555-0222",
        "scheduled_pickup_time": pickup_time.isoformat(),
        "expected_delivery_time": delivery_time.isoformat(),
        "total_weight_kg": 18500.0,
        "package_count": package_count,
        "goods_description": "Precision EV battery subassemblies",
    }
    res = await client.post("/api/v1/shipments", json=payload, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


@pytest.mark.asyncio
async def test_pod_file_upload_and_validation(test_engine):
    """
    Validates file upload, MIME type enforcement, size limits,
    SHA-256 calculation, and controlled-access download.
    """
    client, headers, token, org_id, user_id = await create_user_session(test_engine, "upload")
    shipment = await _create_test_shipment(client, headers)
    shipment_id = shipment["id"]

    # 1. Valid image upload (JPEG)
    fake_jpeg_content = b"\xFF\xD8\xFF\xE0\x00\x10JFIF" + b"A" * 1024
    upload_res = await client.post(
        "/api/v1/pod/upload",
        data={"shipment_id": shipment_id, "category": "delivery_photo"},
        files={"file": ("dock_delivery_photo.jpg", io.BytesIO(fake_jpeg_content), "image/jpeg")},
        headers=headers,
    )
    assert upload_res.status_code == 200, upload_res.text
    file_info = upload_res.json()["file"]
    assert file_info["content_type"] == "image/jpeg"
    assert file_info["file_size_bytes"] == len(fake_jpeg_content)
    assert len(file_info["sha256_hash"]) == 64
    assert "pod/" in file_info["file_key"]
    assert file_info["url"] is not None

    # Test downloading file via controlled-access URL
    download_res = await client.get(file_info["url"])
    assert download_res.status_code == 200
    assert download_res.content == fake_jpeg_content

    # 2. Reject prohibited executable extension
    bad_file = b"MZ\x90\x00\x03\x00\x00\x00"
    bad_res = await client.post(
        "/api/v1/pod/upload",
        data={"shipment_id": shipment_id, "category": "delivery_photo"},
        files={"file": ("malicious.exe", io.BytesIO(bad_file), "application/x-msdownload")},
        headers=headers,
    )
    assert bad_res.status_code in [400, 415]

    # 3. Reject oversized file (>10MB)
    huge_data = b"X" * (11 * 1024 * 1024)
    huge_res = await client.post(
        "/api/v1/pod/upload",
        data={"shipment_id": shipment_id, "category": "delivery_photo"},
        files={"file": ("huge_photo.jpg", io.BytesIO(huge_data), "image/jpeg")},
        headers=headers,
    )
    assert huge_res.status_code == 413


@pytest.mark.asyncio
async def test_mandatory_evidence_validation(test_engine):
    """
    Verifies that missing mandatory evidence (delivery photograph or recipient signature)
    blocks full delivery verification with HTTP 422.
    """
    client, headers, token, org_id, user_id = await create_user_session(test_engine, "mand")
    shipment = await _create_test_shipment(client, headers)
    shipment_id = shipment["id"]

    # 1. Attempt submission without signature or document
    res_no_sig = await client.post(
        f"/api/v1/pod/shipments/{shipment_id}/submit",
        json={
            "recipient_name": "Marcus Aurelius",
            "received_quantity": 100,
            "delivery_photo_urls": ["pod/test/photo1.jpg"],
            # Missing signature_image_url and document_url!
        },
        headers=headers,
    )
    assert res_no_sig.status_code == 422
    assert "Mandatory delivery evidence missing" in res_no_sig.text

    # 2. Attempt submission without delivery photos
    res_no_photo = await client.post(
        f"/api/v1/pod/shipments/{shipment_id}/submit",
        json={
            "recipient_name": "Marcus Aurelius",
            "received_quantity": 100,
            "signature_image_url": "pod/test/signature.png",
            "delivery_photo_urls": [],  # Empty photos!
        },
        headers=headers,
    )
    assert res_no_photo.status_code == 422
    assert "Mandatory delivery evidence missing" in res_no_photo.text

    # 3. Full valid submission with both photo and signature succeeds
    valid_res = await client.post(
        f"/api/v1/pod/shipments/{shipment_id}/submit",
        json={
            "recipient_name": "Marcus Aurelius",
            "recipient_designation": "Receiving Dock Chief",
            "recipient_phone": "+1-614-555-9876",
            "recipient_email": "marcus@columbusdc.com",
            "received_quantity": 100,
            "signature_image_url": "pod/test/signature.png",
            "delivery_photo_urls": ["pod/test/photo1.jpg", "pod/test/photo2.jpg"],
            "latitude": 39.9612,
            "longitude": -82.9988,
            "delivery_location_name": "Columbus Facility Bay 4",
        },
        headers=headers,
    )
    assert valid_res.status_code == 200, valid_res.text
    pod_data = valid_res.json()
    assert pod_data["signed_by_name"] == "Marcus Aurelius"
    assert pod_data["verification_status"] == "PENDING"
    assert pod_data["is_shortage"] is False
    assert pod_data["is_damaged"] is False
    assert len(pod_data["delivery_photo_urls"]) == 2


@pytest.mark.asyncio
async def test_partial_delivery_shortage_discrepancy(test_engine):
    """
    Validates that a partial delivery (received < expected) automatically:
    - Flags POD verification_status as DISCREPANCY_FLAGGED
    - Creates a DeliveryDiscrepancy record of type SHORTAGE
    - Automatically opens an operational exception
    """
    client, headers, token, org_id, user_id = await create_user_session(test_engine, "short")
    # Shipment has 100 packages expected
    shipment = await _create_test_shipment(client, headers, package_count=100)
    shipment_id = shipment["id"]

    # Driver records only 85 packages received (15 missing/shortage)
    pod_res = await client.post(
        f"/api/v1/pod/shipments/{shipment_id}/submit",
        json={
            "recipient_name": "Rachel Zane",
            "received_quantity": 85,
            "signature_image_url": "pod/test/sig_rachel.png",
            "delivery_photo_urls": ["pod/test/dock_pallet.jpg"],
            "shortage_description": "Pallet #4 missing from trailer; only 85 of 100 crates unloaded.",
        },
        headers=headers,
    )
    assert pod_res.status_code == 200, pod_res.text
    pod = pod_res.json()

    assert pod["is_shortage"] is True
    assert pod["shortage_quantity"] == 15
    assert pod["verification_status"] == "DISCREPANCY_FLAGGED"
    assert len(pod["discrepancies"]) >= 1

    shortage_disc = next(d for d in pod["discrepancies"] if d["discrepancy_type"] == "SHORTAGE")
    assert shortage_disc["expected_quantity"] == 100
    assert shortage_disc["received_quantity"] == 85
    assert shortage_disc["variance"] == -15

    # Verify operational exception was automatically created
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        exc_stmt = select(ExceptionRecord).where(
            ExceptionRecord.shipment_id == uuid.UUID(shipment_id),
            ExceptionRecord.exception_type == ExceptionType.DELIVERY_DISCREPANCY,
        )
        exc = (await session.execute(exc_stmt)).scalar_one_or_none()
        assert exc is not None, "DELIVERY_DISCREPANCY exception should be automatically opened"
        assert exc.severity == "HIGH"
        assert "Shortage of 15" in exc.description


@pytest.mark.asyncio
async def test_damaged_delivery_discrepancy(test_engine):
    """
    Validates that reporting damaged cargo automatically:
    - Flags POD as DISCREPANCY_FLAGGED
    - Creates a DAMAGE DeliveryDiscrepancy record
    - Automatically opens an operational exception with appropriate severity
    """
    client, headers, token, org_id, user_id = await create_user_session(test_engine, "damage")
    shipment = await _create_test_shipment(client, headers, package_count=50)
    shipment_id = shipment["id"]

    pod_res = await client.post(
        f"/api/v1/pod/shipments/{shipment_id}/submit",
        json={
            "recipient_name": "Harold Finch",
            "received_quantity": 50,
            "is_damaged": True,
            "damage_severity": "SEVERE",
            "damage_description": "Two pallets tipped over in transit; crushed packaging with leaking fluids.",
            "damage_photo_urls": ["pod/test/damage1.jpg", "pod/test/damage2.jpg"],
            "signature_image_url": "pod/test/sig_harold.png",
            "delivery_photo_urls": ["pod/test/overview.jpg"],
        },
        headers=headers,
    )
    assert pod_res.status_code == 200, pod_res.text
    pod = pod_res.json()

    assert pod["is_damaged"] is True
    assert pod["damage_severity"] == "SEVERE"
    assert pod["verification_status"] == "DISCREPANCY_FLAGGED"

    damage_disc = next(d for d in pod["discrepancies"] if d["discrepancy_type"] == "DAMAGE")
    assert damage_disc["discrepancy_type"] == "DAMAGE"
    assert "Two pallets tipped" in damage_disc["notes"]

    # Verify exception in database has CRITICAL severity due to SEVERE rating
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        exc_stmt = select(ExceptionRecord).where(
            ExceptionRecord.shipment_id == uuid.UUID(shipment_id),
            ExceptionRecord.exception_type == ExceptionType.DELIVERY_DISCREPANCY,
        )
        exc = (await session.execute(exc_stmt)).scalar_one_or_none()
        assert exc is not None
        assert exc.severity == "CRITICAL"


@pytest.mark.asyncio
async def test_immutable_evidence_and_submission_history(test_engine):
    """
    Validates that POD submissions preserve revision history and never permit
    silent modifications to existing evidence.
    """
    client, headers, token, org_id, user_id = await create_user_session(test_engine, "hist")
    shipment = await _create_test_shipment(client, headers)
    shipment_id = shipment["id"]

    # 1. Initial submission
    res1 = await client.post(
        f"/api/v1/pod/shipments/{shipment_id}/submit",
        json={
            "recipient_name": "Original Signer",
            "received_quantity": 100,
            "signature_image_url": "pod/test/sig1.png",
            "delivery_photo_urls": ["pod/test/photo1.jpg"],
        },
        headers=headers,
    )
    assert res1.status_code == 200
    pod1 = res1.json()
    assert len(pod1["submission_history"]) == 1
    assert pod1["submission_history"][0]["action"] == "POD_SUBMITTED"
    assert pod1["is_modified"] is False

    # 2. Resubmission / Addendum with revised recipient contact & notes
    res2 = await client.post(
        f"/api/v1/pod/shipments/{shipment_id}/submit",
        json={
            "recipient_name": "Original Signer",
            "recipient_phone": "+1-555-444-3333",
            "received_quantity": 100,
            "signature_image_url": "pod/test/sig1.png",
            "delivery_photo_urls": ["pod/test/photo1.jpg", "pod/test/supplementary.jpg"],
            "additional_notes": "Added gate stamp photo requested by receiving office.",
        },
        headers=headers,
    )
    assert res2.status_code == 200
    pod2 = res2.json()
    assert len(pod2["submission_history"]) == 2
    assert pod2["submission_history"][1]["action"] == "POD_REVISED"
    assert pod2["is_modified"] is True
    assert pod2["additional_notes"] == "Added gate stamp photo requested by receiving office."


@pytest.mark.asyncio
async def test_manufacturer_review_lifecycle(test_engine):
    """
    Validates manufacturer review actions (APPROVE, REJECT, FLAG_DISCREPANCY).
    """
    client, headers, token, org_id, user_id = await create_user_session(test_engine, "review")
    shipment = await _create_test_shipment(client, headers)
    shipment_id = shipment["id"]

    # Driver submits clean POD
    await client.post(
        f"/api/v1/pod/shipments/{shipment_id}/submit",
        json={
            "recipient_name": "Donna Paulsen",
            "received_quantity": 100,
            "signature_image_url": "pod/test/sig.png",
            "delivery_photo_urls": ["pod/test/delivered.jpg"],
        },
        headers=headers,
    )

    # 1. Reject without reason must fail
    bad_review = await client.post(
        f"/api/v1/pod/shipments/{shipment_id}/review",
        json={"action": "REJECT"},
        headers=headers,
    )
    assert bad_review.status_code == 400

    # 2. Reject with reason
    rej_res = await client.post(
        f"/api/v1/pod/shipments/{shipment_id}/review",
        json={
            "action": "REJECT",
            "rejection_reason": "Recipient signature is unreadable and dock photo is blurry.",
        },
        headers=headers,
    )
    assert rej_res.status_code == 200
    pod_rej = rej_res.json()
    assert pod_rej["verification_status"] == "REJECTED"
    assert "blurry" in pod_rej["rejection_reason"]

    # 3. Approve POD
    app_res = await client.post(
        f"/api/v1/pod/shipments/{shipment_id}/review",
        json={"action": "APPROVE", "notes": "Re-verified with facility manager via phone."},
        headers=headers,
    )
    assert app_res.status_code == 200
    pod_app = app_res.json()
    assert pod_app["verification_status"] == "VERIFIED"
    assert pod_app["verified_at"] is not None
    assert pod_app["verified_by_user_id"] == user_id


@pytest.mark.asyncio
async def test_cross_tenant_isolation_on_pod(test_engine):
    """
    Validates that organizations cannot view or review PODs belonging to other tenants.
    """
    client_a, headers_a, _, org_a, _ = await create_user_session(test_engine, "tenant_a")
    client_b, headers_b, _, org_b, _ = await create_user_session(test_engine, "tenant_b")

    shipment_a = await _create_test_shipment(client_a, headers_a)
    shipment_id_a = shipment_a["id"]

    await client_a.post(
        f"/api/v1/pod/shipments/{shipment_id_a}/submit",
        json={
            "recipient_name": "Tenant A Consignee",
            "received_quantity": 100,
            "signature_image_url": "pod/test/sig.png",
            "delivery_photo_urls": ["pod/test/cargo.jpg"],
        },
        headers=headers_a,
    )

    # Tenant B tries to view Tenant A's POD
    get_res = await client_b.get(f"/api/v1/pod/shipments/{shipment_id_a}", headers=headers_b)
    assert get_res.status_code in [403, 404]

    # Tenant B tries to review Tenant A's POD
    rev_res = await client_b.post(
        f"/api/v1/pod/shipments/{shipment_id_a}/review",
        json={"action": "APPROVE"},
        headers=headers_b,
    )
    assert rev_res.status_code in [403, 404]
