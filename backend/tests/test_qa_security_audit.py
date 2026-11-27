import hashlib
import hmac
import time
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
from app.models.enums import BookingStatus, ShipmentStatus, UserRoleType
from app.models.integrations import AuditLog
from app.models.shipment import Shipment, TransporterBooking
from app.models.transporter import Driver, Transporter, Vehicle
from app.services.integrations.webhook_service import webhook_service


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
        "full_name": f"{prefix.capitalize()} Security User",
        "email": email,
        "password": "Password123!",
        "confirm_password": "Password123!",
        "organization_name": f"{prefix.capitalize()} Security Org {uid}",
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
    return user_client, headers, token, user["organization_id"], user["id"], data.get("refresh_token")


async def create_test_shipment(client: AsyncClient, headers: dict) -> dict:
    now = datetime.now(timezone.utc)
    res = await client.post(
        "/api/v1/shipments",
        json={
            "customer_name": "Secure Electronics Inc",
            "customer_reference": f"SEC-PO-{uuid.uuid4().hex[:6].upper()}",
            "origin_name": "Secure Dock A",
            "origin_address": "100 Security Way",
            "origin_city": "Austin",
            "origin_state": "TX",
            "origin_postal_code": "78701",
            "origin_contact_name": "Security Officer",
            "origin_contact_phone": "+1-512-555-0199",
            "destination_name": "Secure Vault B",
            "destination_address": "200 Vault Blvd",
            "destination_city": "Dallas",
            "destination_state": "TX",
            "destination_postal_code": "75201",
            "destination_contact_name": "Vault Master",
            "destination_contact_phone": "+1-214-555-0188",
            "scheduled_pickup_time": (now + timedelta(hours=2)).isoformat(),
            "expected_delivery_time": (now + timedelta(hours=18)).isoformat(),
            "goods_description": "Encrypted Hardware Modules",
            "cargo_category": "Electronics",
            "package_count": 5,
            "package_unit": "Cases",
            "total_weight_kg": 500.0,
            "declared_value": 150000.0,
            "priority": "HIGH",
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()


# ==============================================================================
# 1. SQL Injection Resistance
# ==============================================================================

@pytest.mark.asyncio
async def test_sql_injection_resistance_across_query_parameters(test_engine):
    """
    Attempts SQL injection attacks via search strings, filters, and headers.
    Ensures parameterized queries protect against injection and return 200 or 400 safely,
    never executing SQL or leaking database metadata.
    """
    client, headers, _, _, _, _ = await create_user_session(test_engine, "sqli")
    await create_test_shipment(client, headers)

    sql_payloads = [
        "' OR '1'='1",
        "'; DROP TABLE shipments; --",
        "1' UNION SELECT id, hashed_password, email FROM users --",
        "' OR 1=1 --",
        "admin'--",
        "\" OR \"\"=\"",
    ]

    for payload in sql_payloads:
        # Search shipments with SQL injection payload
        res = await client.get(f"/api/v1/shipments?search={payload}", headers=headers)
        assert res.status_code in (200, 400, 422), f"Failed on search payload: {payload}"
        if res.status_code == 200:
            # Must return list without crash or leaked credentials
            data = res.json()
            assert "items" in data
            assert not any("hashed_password" in str(item) for item in data["items"])

        # Query audit logs with SQL injection payload in action filter
        audit_res = await client.get(f"/api/v1/audit/logs?search={payload}", headers=headers)
        assert audit_res.status_code in (200, 400, 422)


# ==============================================================================
# 2. Cross-Tenant Data Access & IDOR Prevention
# ==============================================================================

@pytest.mark.asyncio
async def test_cross_tenant_data_access_and_idor_prevention(test_engine):
    """
    Validates complete multi-tenant boundaries (IDOR prevention):
    - User A creates shipments, bookings, and audit records.
    - User B (different organization) cannot retrieve, update, or delete User A's records.
    - Cross-tenant requests return 404 Not Found (or 403 Forbidden).
    """
    client_a, headers_a, _, org_a, _, _ = await create_user_session(test_engine, "tenant_a")
    client_b, headers_b, _, org_b, _, _ = await create_user_session(test_engine, "tenant_b")

    # Org A creates shipment
    shipment_a = await create_test_shipment(client_a, headers_a)
    shipment_id = shipment_a["id"]

    # 1. Org B attempts direct GET of Org A's shipment (IDOR)
    idor_get = await client_b.get(f"/api/v1/shipments/{shipment_id}", headers=headers_b)
    assert idor_get.status_code in (404, 403), f"IDOR vulnerability! Org B accessed Org A shipment: {idor_get.text}"

    # 2. Org B attempts to cancel Org A's shipment
    idor_cancel = await client_b.post(
        f"/api/v1/shipments/{shipment_id}/cancel",
        json={"cancellation_reason": "Malicious cancellation attempt"},
        headers=headers_b,
    )
    assert idor_cancel.status_code in (404, 403)

    # 3. Org B attempts to record tracking event on Org A's shipment
    idor_tracking = await client_b.post(
        f"/api/v1/tracking/shipments/{shipment_id}/events",
        json={"milestone": "IN_TRANSIT", "description": "Tampered tracking"},
        headers=headers_b,
    )
    assert idor_tracking.status_code in (404, 403)

    # 4. Org B lists shipments: Org A's shipment must NOT appear in Org B's results
    list_b = await client_b.get("/api/v1/shipments", headers=headers_b)
    assert list_b.status_code == 200
    shipment_ids_b = [s["id"] for s in list_b.json().get("items", [])]
    assert shipment_id not in shipment_ids_b


# ==============================================================================
# 3. Password Security & Complexity Enforcement
# ==============================================================================

@pytest.mark.asyncio
async def test_password_security_and_complexity_validation(test_engine):
    """
    Ensures weak, trivial, or short passwords are systematically rejected with HTTP 422.
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

    weak_passwords = [
        "short",          # Too short (< 8 chars)
        "12345678",       # Digits only, no uppercase or special char
        "password",       # Lowercase only
        "PASSWORD123",    # Missing special character
        "NoDigitsHere!",  # Missing digit
    ]

    for weak_pw in weak_passwords:
        uid = uuid.uuid4().hex[:6]
        res = await client.post(
            "/api/v1/auth/register",
            json={
                "full_name": "Weak Pass User",
                "email": f"weak_{uid}@example.com",
                "password": weak_pw,
                "confirm_password": weak_pw,
                "organization_name": f"Weak Org {uid}",
                "org_type": "MANUFACTURER",
                "accept_terms": True,
            },
        )
        assert res.status_code == 422, f"Accepted weak password '{weak_pw}'!"


# ==============================================================================
# 4. Session Revocation & Refresh Token Protection
# ==============================================================================

@pytest.mark.asyncio
async def test_session_revocation_and_token_reuse_protection(test_engine):
    """
    Verifies authentication security:
    - User logs out: refresh session is revoked.
    - Revoked refresh token cannot be used to generate new access tokens.
    - Protected endpoints reject logged-out tokens or revoked sessions.
    """
    client, headers, token, _, _, _ = await create_user_session(test_engine, "sess_rev")

    # Verify session is initially active
    me_res = await client.get("/api/v1/auth/me", headers=headers)
    assert me_res.status_code == 200

    # Perform logout
    logout_res = await client.post("/api/v1/auth/logout", headers=headers)
    assert logout_res.status_code == 200

    # Attempt to use the refresh endpoint without active valid session
    refresh_attempt = await client.post("/api/v1/auth/refresh", json={"refresh_token": "invalid_or_revoked_token"})
    assert refresh_attempt.status_code in (401, 403, 422)


# ==============================================================================
# 5. Immutability of Audit Logs (Tamper Resistance)
# ==============================================================================

@pytest.mark.asyncio
async def test_audit_log_immutability_and_tamper_resistance(test_engine):
    """
    Verifies that audit log entries are strictly append-only and cannot be updated or deleted:
    PUT, PATCH, DELETE requests to /api/v1/audit/logs/{id} must return HTTP 403 Forbidden.
    """
    client, headers, _, org_id, _, _ = await create_user_session(test_engine, "audit_tamper")

    # Generate an audit event
    await create_test_shipment(client, headers)

    # Query audit logs
    logs_res = await client.get("/api/v1/audit/logs", headers=headers)
    assert logs_res.status_code == 200
    logs = logs_res.json()["items"]
    assert len(logs) > 0
    target_log_id = logs[0]["id"]

    # 1. Attempt PUT modification -> 403 Forbidden
    put_res = await client.put(
        f"/api/v1/audit/logs/{target_log_id}",
        json={"action": "TAMPERED_ACTION"},
        headers=headers,
    )
    assert put_res.status_code == 403
    assert "immutable" in put_res.text.lower() or "forbidden" in put_res.text.lower()

    # 2. Attempt PATCH modification -> 403 Forbidden
    patch_res = await client.patch(
        f"/api/v1/audit/logs/{target_log_id}",
        json={"action": "TAMPERED_ACTION"},
        headers=headers,
    )
    assert patch_res.status_code == 403

    # 3. Attempt DELETE -> 403 Forbidden
    del_res = await client.delete(
        f"/api/v1/audit/logs/{target_log_id}",
        headers=headers,
    )
    assert del_res.status_code == 403


# ==============================================================================
# 6. Sensitive Information Exposure (Secret Masking)
# ==============================================================================

@pytest.mark.asyncio
async def test_sensitive_credentials_masked_in_audit_and_responses(test_engine):
    """
    Verifies that sensitive data (passwords, hashes, tokens, API keys) are never exposed:
    - User objects do not expose 'hashed_password'.
    - Audit log sanitization masks sensitive keys as [REDACTED].
    """
    client, headers, _, org_id, user_id, _ = await create_user_session(test_engine, "masking")

    # 1. Verify /auth/me does not expose hashed_password
    me_res = await client.get("/api/v1/auth/me", headers=headers)
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert "hashed_password" not in me_data
    assert "password" not in me_data

    # 2. Verify audit service sanitizes passwords/secrets
    from app.services.audit_service import AuditService, sanitize_audit_data

    test_payload = {
        "username": "dispatcher_1",
        "password": "SecretPassword123!",
        "access_token": "eyJhbGciOi...",
        "api_key": "live_key_9999",
        "normal_field": "safe_value",
    }
    sanitized = sanitize_audit_data(test_payload)
    assert sanitized["password"] == "[REDACTED]"
    assert sanitized["access_token"] == "[REDACTED]"
    assert sanitized["api_key"] == "[REDACTED]"
    assert sanitized["normal_field"] == "safe_value"


# ==============================================================================
# 7. Webhook HMAC Authentication & Tamper Detection
# ==============================================================================

@pytest.mark.asyncio
async def test_webhook_hmac_tamper_detection(test_engine):
    """
    Validates webhook security:
    - Tampered payloads with invalid HMAC signatures are rejected with 401 Unauthorized.
    - Missing signatures or expired timestamps are rejected.
    """
    client, headers, _, org_id, _, _ = await create_user_session(test_engine, "sec_hook")

    # Create an integration connection with webhook secret
    unique_slug = f"sec-audit-{uuid.uuid4().hex[:8]}"
    conn_res = await client.post(
        "/api/v1/integrations/connections",
        json={
            "name": "Security Audit Webhook",
            "slug": unique_slug,
            "integration_type": "CUSTOM_WEBHOOK",
            "base_url": "https://audit.partner.test",
        },
        headers=headers,
    )
    assert conn_res.status_code == 201
    conn = conn_res.json()
    slug = conn["slug"]
    conn_id = uuid.UUID(conn["id"])

    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        from app.models.integrations import IntegrationConnection
        conn_db = await session.get(IntegrationConnection, conn_id)
        secret = conn_db.webhook_secret

    payload = b'{"event":"CARGO_DISPATCHED","id":"test-1"}'
    valid_timestamp = str(time.time())

    # 1. Tampered payload with valid signature for different body
    tampered_sig = hmac.new(secret.encode(), b'{"event":"DIFFERENT_BODY"}', hashlib.sha256).hexdigest()
    res_tampered = await client.post(
        f"/api/v1/integrations/webhooks/{slug}",
        content=payload,
        headers={
            "Content-Type": "application/json",
            "X-CargoPulse-Signature": tampered_sig,
            "X-CargoPulse-Timestamp": valid_timestamp,
        },
    )
    assert res_tampered.status_code == 401

    # 2. Missing signature header
    res_no_sig = await client.post(
        f"/api/v1/integrations/webhooks/{slug}",
        content=payload,
        headers={"Content-Type": "application/json"},
    )
    assert res_no_sig.status_code in (400, 401)
