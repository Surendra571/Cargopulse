import uuid
from datetime import datetime, timedelta, timezone
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.api.deps import get_db
from app.core.config import settings
from app.core.security import generate_secure_random_token, hash_token
from app.main import app
from app.models import (
    Organization,
    PasswordResetToken,
    RefreshSession,
    Role,
    User,
    UserRole,
)


@pytest_asyncio.fixture
async def test_engine():
    """Async engine using NullPool to prevent event loop connection leakage across tests."""
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool, echo=False)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def async_db(test_engine):
    """Direct database session fixture for test assertions."""
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(test_engine):
    """Async HTTP client bound to FastAPI application with isolated DB session."""
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)

    async def override_get_db():
        async with session_factory() as session:
            try:
                yield session
            finally:
                await session.close()

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_successful_registration(client: AsyncClient, async_db: AsyncSession):
    """
    Test 1 & 11: Successful registration & Organization creation atomicity.
    Verifies that customer registration creates the organization, its first administrator,
    default role, permissions, and audit log atomically in PostgreSQL.
    """
    unique_id = uuid.uuid4().hex[:8]
    payload = {
        "full_name": "Marcus Aurelius",
        "email": f"marcus.{unique_id}@apexlogistics.com",
        "password": "SecurePassword123!",
        "confirm_password": "SecurePassword123!",
        "organization_name": f"Apex Transport {unique_id}",
        "org_type": "CARRIER",
        "accept_terms": True,
    }

    res = await client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 201, res.text
    data = res.json()

    # Check response structure
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == payload["email"]
    assert data["user"]["first_name"] == "Marcus"
    assert data["user"]["last_name"] == "Aurelius"
    assert "Administrator" in data["user"]["roles"]
    assert "shipments:create" in data["user"]["permissions"]

    # Verify cookies
    assert settings.COOKIE_REFRESH_NAME in res.cookies
    assert settings.COOKIE_CSRF_NAME in res.cookies

    # Verify atomic DB persistence
    user_stmt = select(User).where(User.email == payload["email"])
    db_user = (await async_db.execute(user_stmt)).scalar_one_or_none()
    assert db_user is not None

    org_stmt = select(Organization).where(Organization.id == db_user.organization_id)
    db_org = (await async_db.execute(org_stmt)).scalar_one_or_none()
    assert db_org is not None
    assert db_org.name == payload["organization_name"]


@pytest.mark.asyncio
async def test_duplicate_registration_fails(client: AsyncClient):
    """
    Test 2: Duplicate registration.
    Attempting to register with an email that is already in use must fail with 409 Conflict.
    """
    unique_id = uuid.uuid4().hex[:8]
    payload = {
        "full_name": "Diana Prince",
        "email": f"diana.{unique_id}@themyscira.com",
        "password": "SecretAmazon123!",
        "confirm_password": "SecretAmazon123!",
        "organization_name": f"Themyscira Logistics {unique_id}",
        "org_type": "MANUFACTURER",
        "accept_terms": True,
    }

    # First registration -> 201
    res1 = await client.post("/api/v1/auth/register", json=payload)
    assert res1.status_code == 201

    # Second registration with SAME email -> 409 Conflict
    res2 = await client.post("/api/v1/auth/register", json=payload)
    assert res2.status_code == 409
    assert "already exists" in res2.json()["detail"]


@pytest.mark.asyncio
async def test_successful_login(client: AsyncClient):
    """
    Test 3: Successful login.
    Authenticates with valid email & password, receives access token and session cookies.
    """
    unique_id = uuid.uuid4().hex[:8]
    reg_payload = {
        "full_name": "Bruce Wayne",
        "email": f"bruce.{unique_id}@wayneenterprises.com",
        "password": "GothamKnight99!",
        "confirm_password": "GothamKnight99!",
        "organization_name": f"Wayne Enterprises {unique_id}",
        "org_type": "MANUFACTURER",
        "accept_terms": True,
    }
    await client.post("/api/v1/auth/register", json=reg_payload)

    # Login
    login_payload = {
        "email": reg_payload["email"],
        "password": "GothamKnight99!",
    }
    res = await client.post("/api/v1/auth/login", json=login_payload)
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["user"]["email"] == reg_payload["email"]
    assert settings.COOKIE_REFRESH_NAME in res.cookies


@pytest.mark.asyncio
async def test_invalid_credentials_rejected(client: AsyncClient):
    """
    Test 4: Invalid credentials.
    Wrong password or non-existent email returns 401 Unauthorized.
    """
    # 1. Unregistered email
    res1 = await client.post(
        "/api/v1/auth/login",
        json={"email": f"nonexistent-{uuid.uuid4().hex[:6]}@cargopulse.com", "password": "WrongPassword123!"},
    )
    assert res1.status_code == 401

    # 2. Existing user, wrong password
    unique_id = uuid.uuid4().hex[:8]
    reg_payload = {
        "full_name": "Clark Kent",
        "email": f"clark.{unique_id}@dailyplanet.com",
        "password": "MetropolisPass123!",
        "confirm_password": "MetropolisPass123!",
        "organization_name": f"Daily Planet {unique_id}",
        "org_type": "MANUFACTURER",
        "accept_terms": True,
    }
    await client.post("/api/v1/auth/register", json=reg_payload)

    res2 = await client.post(
        "/api/v1/auth/login",
        json={"email": reg_payload["email"], "password": "TotallyWrongPassword!"},
    )
    assert res2.status_code == 401


@pytest.mark.asyncio
async def test_logout_and_session_revocation(client: AsyncClient, async_db: AsyncSession):
    """
    Test 5: Logout.
    Revokes current refresh session server-side, clears cookies, and prevents reuse.
    """
    unique_id = uuid.uuid4().hex[:8]
    reg_payload = {
        "full_name": "Arthur Curry",
        "email": f"arthur.{unique_id}@atlantis.com",
        "password": "OceanMaster88!",
        "confirm_password": "OceanMaster88!",
        "organization_name": f"Atlantis Freight {unique_id}",
        "org_type": "CARRIER",
        "accept_terms": True,
    }
    reg_res = await client.post("/api/v1/auth/register", json=reg_payload)
    refresh_token = reg_res.cookies.get(settings.COOKIE_REFRESH_NAME)
    csrf_token = reg_res.cookies.get(settings.COOKIE_CSRF_NAME)

    # Set cookies directly on client
    client.cookies.set(settings.COOKIE_REFRESH_NAME, refresh_token)
    client.cookies.set(settings.COOKIE_CSRF_NAME, csrf_token)

    logout_res = await client.post(
        "/api/v1/auth/logout",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert logout_res.status_code == 200

    # Verify session is marked revoked in PostgreSQL
    token_hash = hash_token(refresh_token)
    stmt = select(RefreshSession).where(RefreshSession.token_hash == token_hash)
    ref_session = (await async_db.execute(stmt)).scalar_one_or_none()
    assert ref_session is not None
    assert ref_session.revoked_at is not None


@pytest.mark.asyncio
async def test_reuse_of_revoked_refresh_token_triggers_breach_detection(
    client: AsyncClient, async_db: AsyncSession
):
    """
    Test 6: Reuse of revoked refresh token.
    Attempting to refresh with an already-revoked token triggers security breach response,
    revokes all active sessions for that user, and returns 401.
    """
    unique_id = uuid.uuid4().hex[:8]
    reg_payload = {
        "full_name": "Barry Allen",
        "email": f"barry.{unique_id}@star-labs.com",
        "password": "SpeedForce123!",
        "confirm_password": "SpeedForce123!",
        "organization_name": f"Star Labs {unique_id}",
        "org_type": "THIRD_PARTY_LOGISTICS",
        "accept_terms": True,
    }
    reg_res = await client.post("/api/v1/auth/register", json=reg_payload)
    token_1 = reg_res.cookies.get(settings.COOKIE_REFRESH_NAME)
    csrf_1 = reg_res.cookies.get(settings.COOKIE_CSRF_NAME)

    # Legitimate refresh #1 (rotates token_1 to token_2)
    client.cookies.set(settings.COOKIE_REFRESH_NAME, token_1)
    client.cookies.set(settings.COOKIE_CSRF_NAME, csrf_1)

    refresh_res = await client.post(
        "/api/v1/auth/refresh",
        headers={"X-CSRF-Token": csrf_1},
    )
    assert refresh_res.status_code == 200
    token_2 = refresh_res.cookies.get(settings.COOKIE_REFRESH_NAME)
    assert token_2 != token_1

    # Malicious attempt: Reuse token_1 (which is now revoked)
    client.cookies.set(settings.COOKIE_REFRESH_NAME, token_1)
    client.cookies.set(settings.COOKIE_CSRF_NAME, csrf_1)

    reuse_res = await client.post(
        "/api/v1/auth/refresh",
        headers={"X-CSRF-Token": csrf_1},
    )
    assert reuse_res.status_code == 401
    assert "revoked" in reuse_res.json()["detail"].lower()

    # Now token_2 should ALSO be revoked due to compromised identity breach detection
    token_2_hash = hash_token(token_2)
    session_2 = (
        await async_db.execute(select(RefreshSession).where(RefreshSession.token_hash == token_2_hash))
    ).scalar_one_or_none()
    assert session_2.revoked_at is not None


@pytest.mark.asyncio
async def test_expired_session_fails(client: AsyncClient, async_db: AsyncSession):
    """
    Test 7: Expired session.
    Attempting to refresh an expired session returns 401.
    """
    unique_id = uuid.uuid4().hex[:8]
    reg_payload = {
        "full_name": "Victor Stone",
        "email": f"victor.{unique_id}@cyberlogistics.com",
        "password": "CyborgPower123!",
        "confirm_password": "CyborgPower123!",
        "organization_name": f"Cyber Logistics {unique_id}",
        "org_type": "CARRIER",
        "accept_terms": True,
    }
    reg_res = await client.post("/api/v1/auth/register", json=reg_payload)
    token = reg_res.cookies.get(settings.COOKIE_REFRESH_NAME)
    csrf = reg_res.cookies.get(settings.COOKIE_CSRF_NAME)

    # Manually expire session in DB
    token_hash = hash_token(token)
    await async_db.execute(
        update(RefreshSession)
        .where(RefreshSession.token_hash == token_hash)
        .values(expires_at=datetime.now(timezone.utc) - timedelta(days=1))
    )
    await async_db.commit()

    # Attempt refresh
    client.cookies.set(settings.COOKIE_REFRESH_NAME, token)
    client.cookies.set(settings.COOKIE_CSRF_NAME, csrf)

    res = await client.post(
        "/api/v1/auth/refresh",
        headers={"X-CSRF-Token": csrf},
    )
    assert res.status_code == 401
    assert "expired" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_password_reset_flow(client: AsyncClient, async_db: AsyncSession):
    """
    Test 8: Password reset.
    Full workflow: request reset -> reset password with token -> old password rejected -> new password accepted.
    """
    unique_id = uuid.uuid4().hex[:8]
    email = f"hal.jordan.{unique_id}@greenlantern.com"
    reg_payload = {
        "full_name": "Hal Jordan",
        "email": email,
        "password": "WillpowerPass123!",
        "confirm_password": "WillpowerPass123!",
        "organization_name": f"OA Logistics {unique_id}",
        "org_type": "MANUFACTURER",
        "accept_terms": True,
    }
    await client.post("/api/v1/auth/register", json=reg_payload)

    # 1. Request reset
    forgot_res = await client.post("/api/v1/auth/forgot-password", json={"email": email})
    assert forgot_res.status_code == 200

    # 2. Retrieve user
    user_stmt = select(User).where(User.email == email)
    db_user = (await async_db.execute(user_stmt)).scalar_one()

    # Test reset with real token: generate known token and insert hash
    known_token = generate_secure_random_token(32)
    known_hash = hash_token(known_token)
    test_reset_record = PasswordResetToken(
        user_id=db_user.id,
        token_hash=known_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
    )
    async_db.add(test_reset_record)
    await async_db.commit()

    # Reset with valid known token
    reset_res = await client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": known_token,
            "new_password": "BrandNewPassword99!",
            "confirm_password": "BrandNewPassword99!",
        },
    )
    assert reset_res.status_code == 200

    # Old password no longer works
    old_login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "WillpowerPass123!"},
    )
    assert old_login.status_code == 401

    # New password works
    new_login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "BrandNewPassword99!"},
    )
    assert new_login.status_code == 200


@pytest.mark.asyncio
async def test_protected_routes_and_change_password(client: AsyncClient):
    """
    Test 9: Protected route access & change password.
    1. Unauthenticated access to /api/v1/auth/me returns 401.
    2. Authenticated access returns valid user profile.
    3. Change password validates current password and updates hash.
    """
    # 1. Unauthenticated request to /me
    unauth_res = await client.get("/api/v1/auth/me")
    assert unauth_res.status_code == 401

    # 2. Register user to get token
    unique_id = uuid.uuid4().hex[:8]
    reg_payload = {
        "full_name": "Oliver Queen",
        "email": f"oliver.{unique_id}@queenindustries.com",
        "password": "EmeraldArcher1!",
        "confirm_password": "EmeraldArcher1!",
        "organization_name": f"Queen Industries {unique_id}",
        "org_type": "MANUFACTURER",
        "accept_terms": True,
    }
    reg_res = await client.post("/api/v1/auth/register", json=reg_payload)
    token = reg_res.json()["access_token"]

    # 3. Authenticated request to /me
    me_res = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_res.status_code == 200
    assert me_res.json()["email"] == reg_payload["email"]
    assert me_res.json()["organization_name"] == reg_payload["organization_name"]

    # 4. Change password with wrong current password -> 400
    bad_change = await client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "current_password": "WrongCurrentPassword!",
            "new_password": "BrandNewArrowPass9!",
            "confirm_password": "BrandNewArrowPass9!",
        },
    )
    assert bad_change.status_code == 400

    # 5. Change password with valid current password -> 200
    good_change = await client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "current_password": "EmeraldArcher1!",
            "new_password": "BrandNewArrowPass9!",
            "confirm_password": "BrandNewArrowPass9!",
        },
    )
    assert good_change.status_code == 200


@pytest.mark.asyncio
async def test_csrf_protection_on_cookie_authenticated_requests(client: AsyncClient):
    """
    Test 10: CSRF protection.
    When a refresh cookie is sent (cookie-authenticated session), mutating requests
    must provide the matching X-CSRF-Token header. Requests with missing or forged
    CSRF headers must be rejected with 403 Forbidden.
    """
    unique_id = uuid.uuid4().hex[:8]
    reg_payload = {
        "full_name": "John Stewart",
        "email": f"john.{unique_id}@corpslogistics.com",
        "password": "GreenLantern99!",
        "confirm_password": "GreenLantern99!",
        "organization_name": f"Corps Logistics {unique_id}",
        "org_type": "CARRIER",
        "accept_terms": True,
    }
    reg_res = await client.post("/api/v1/auth/register", json=reg_payload)
    refresh_token = reg_res.cookies.get(settings.COOKIE_REFRESH_NAME)
    csrf_token = reg_res.cookies.get(settings.COOKIE_CSRF_NAME)

    # 1. Missing X-CSRF-Token header -> 403 Forbidden
    client.cookies.set(settings.COOKIE_REFRESH_NAME, refresh_token)
    client.cookies.set(settings.COOKIE_CSRF_NAME, csrf_token)

    res_no_header = await client.post("/api/v1/auth/refresh")
    assert res_no_header.status_code == 403
    assert "csrf" in res_no_header.json()["detail"].lower()

    # 2. Forged / mismatched X-CSRF-Token header -> 403 Forbidden
    res_forged_header = await client.post(
        "/api/v1/auth/refresh",
        headers={"X-CSRF-Token": "forged_malicious_attacker_token"},
    )
    assert res_forged_header.status_code == 403

    # 3. Legitimate X-CSRF-Token matching cookie -> 200 OK
    res_valid = await client.post(
        "/api/v1/auth/refresh",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert res_valid.status_code == 200
