import uuid
from datetime import datetime, timezone
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.api.deps import get_db
from app.core.config import settings
from app.main import app
from app.models import (
    Organization,
    OrganizationTransporter,
    RefreshSession,
    Role,
    Transporter,
    User,
    UserRole,
    UserRoleType,
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


async def create_user_session(test_engine, prefix: str):
    """Helper to create an isolated HTTP client and authenticated user."""
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
        "full_name": f"{prefix.capitalize()} Admin",
        "email": email,
        "password": "Password123!",
        "confirm_password": "Password123!",
        "organization_name": f"{prefix.capitalize()} Enterprise {uid}",
        "org_type": "MANUFACTURER",
        "accept_terms": True,
    }
    resp = await user_client.post("/api/v1/auth/register", json=reg_payload)
    assert resp.status_code == 201
    data = resp.json()
    token = data["access_token"]
    user = data["user"]
    csrf_token = resp.cookies.get(settings.COOKIE_CSRF_NAME)
    headers = {"Authorization": f"Bearer {token}"}
    if csrf_token:
        headers["X-CSRF-Token"] = csrf_token
    return user_client, user, headers, email


@pytest.mark.asyncio
async def test_organization_profile_and_settings(test_engine):
    """Verifies retrieval and update of organization profile and custom settings."""
    client, user, headers, _ = await create_user_session(test_engine, "org_test")
    try:
        # 1. Get profile
        resp = await client.get("/api/v1/organizations/me", headers=headers)
        assert resp.status_code == 200
        profile = resp.json()
        assert profile["id"] == str(user["organization_id"])
        assert "Enterprise" in profile["name"]

        # 2. Update profile
        upd_resp = await client.put(
            "/api/v1/organizations/me",
            headers=headers,
            json={"name": "Updated Org Name", "tax_identifier": "TAX-998877"},
        )
        assert upd_resp.status_code == 200
        updated_profile = upd_resp.json()
        assert updated_profile["name"] == "Updated Org Name"
        assert updated_profile["tax_identifier"] == "TAX-998877"

        # 3. Get settings
        settings_resp = await client.get("/api/v1/organizations/me/settings", headers=headers)
        assert settings_resp.status_code == 200

        # 4. Patch settings
        new_settings = {"default_sla_hours": 4, "auto_dispatch": True}
        patch_resp = await client.patch(
            "/api/v1/organizations/me/settings",
            headers=headers,
            json={"settings": new_settings},
        )
        assert patch_resp.status_code == 200
        saved_settings = patch_resp.json()
        assert saved_settings["default_sla_hours"] == 4
        assert saved_settings["auto_dispatch"] is True
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_roles_and_permissions_directory(test_engine):
    """Verifies listing roles and permissions available to a tenant."""
    client, _, headers, _ = await create_user_session(test_engine, "roles_test")
    try:
        # List roles
        roles_resp = await client.get("/api/v1/organizations/me/roles", headers=headers)
        assert roles_resp.status_code == 200
        roles = roles_resp.json()
        role_types = [r["role_type"] for r in roles]
        assert "ORGANIZATION_ADMIN" in role_types
        assert "DISPATCH_MANAGER" in role_types
        assert "OPERATIONS_MANAGER" in role_types
        assert "TRANSPORTER_ADMIN" in role_types
        assert "DRIVER" in role_types

        # Ensure SUPER_ADMIN role is not returned for non-superadmin
        assert "SUPER_ADMIN" not in role_types

        # List permissions
        perms_resp = await client.get("/api/v1/organizations/me/permissions", headers=headers)
        assert perms_resp.status_code == 200
        perms = perms_resp.json()
        codes = [p["code"] for p in perms]
        assert "shipments:create" in codes
        assert "organization:manage" in codes
        assert "users:manage" in codes
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_user_lifecycle_and_rbac(test_engine, async_db: AsyncSession):
    """Verifies user invitation, role assignment, status updates, and session termination."""
    client, admin_user, headers, _ = await create_user_session(test_engine, "lifecycle")
    try:
        # Fetch available roles to get Dispatch Manager and Operations Manager IDs
        roles_resp = await client.get("/api/v1/organizations/me/roles", headers=headers)
        roles = roles_resp.json()
        dispatch_role = next(r for r in roles if r["role_type"] == "DISPATCH_MANAGER")
        ops_role = next(r for r in roles if r["role_type"] == "OPERATIONS_MANAGER")

        # 1. Invite a new Dispatch Manager
        invite_payload = {
            "email": f"dispatcher_{uuid.uuid4().hex[:6]}@example.com",
            "first_name": "Dave",
            "last_name": "Dispatcher",
            "phone": "+1987654321",
            "role_ids": [dispatch_role["id"]],
            "initial_password": "DispatchedPass123!",
        }
        invite_resp = await client.post(
            "/api/v1/organizations/me/users",
            headers=headers,
            json=invite_payload,
        )
        assert invite_resp.status_code == 201
        invited_user = invite_resp.json()
        assert invited_user["email"] == invite_payload["email"]
        assert "Dispatch Manager" in invited_user["roles"]
        assert invited_user["is_active"] is True
        invited_user_id = invited_user["id"]

        # 2. Authenticate as the newly invited Dispatch Manager in an isolated client
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as dispatcher_client:
            login_resp = await dispatcher_client.post(
                "/api/v1/auth/login",
                json={"email": invite_payload["email"], "password": "DispatchedPass123!"},
            )
            assert login_resp.status_code == 200
            dispatcher_token = login_resp.json()["access_token"]
            dispatcher_headers = {"Authorization": f"Bearer {dispatcher_token}"}

            # 3. Verify Dispatch Manager CANNOT manage users (403 Forbidden)
            forbidden_resp = await dispatcher_client.get(
                "/api/v1/organizations/me/users",
                headers=dispatcher_headers,
            )
            assert forbidden_resp.status_code == 403

        # 4. Admin updates user roles: add Operations Manager
        update_roles_resp = await client.put(
            f"/api/v1/organizations/me/users/{invited_user_id}/roles",
            headers=headers,
            json={"role_ids": [dispatch_role["id"], ops_role["id"]]},
        )
        assert update_roles_resp.status_code == 200
        updated_user = update_roles_resp.json()
        assert len(updated_user["roles"]) == 2

        # 5. Deactivate user and verify active refresh sessions are revoked
        deact_resp = await client.patch(
            f"/api/v1/organizations/me/users/{invited_user_id}/status",
            headers=headers,
            json={"is_active": False},
        )
        assert deact_resp.status_code == 200
        assert deact_resp.json()["is_active"] is False

        # Check database: sessions for this user must be revoked
        revoked_stmt = select(RefreshSession).where(
            RefreshSession.user_id == uuid.UUID(invited_user_id),
            RefreshSession.revoked_at.isnot(None),
        )
        revoked_sessions = (await async_db.execute(revoked_stmt)).scalars().all()
        assert len(revoked_sessions) >= 1

        # 6. Revoke (soft-delete) user access permanently
        del_resp = await client.delete(
            f"/api/v1/organizations/me/users/{invited_user_id}",
            headers=headers,
        )
        assert del_resp.status_code == 200

        # User no longer appears in active user list
        users_list = (await client.get("/api/v1/organizations/me/users", headers=headers)).json()
        assert not any(u["id"] == invited_user_id for u in users_list)
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_privilege_escalation_prevention(test_engine, async_db: AsyncSession):
    """Verifies that an Organization Admin cannot assign SUPER_ADMIN or self-deactivate."""
    client, admin_user, headers, _ = await create_user_session(test_engine, "escalate")
    try:
        # Manually insert a SUPER_ADMIN system role into DB if not present
        super_role_stmt = select(Role).where(Role.role_type == UserRoleType.SUPER_ADMIN)
        super_role = (await async_db.execute(super_role_stmt)).scalar_one_or_none()
        if not super_role:
            super_role = Role(
                name="Super Administrator",
                role_type=UserRoleType.SUPER_ADMIN,
                is_system_role=True,
            )
            async_db.add(super_role)
            await async_db.commit()
            await async_db.refresh(super_role)

        # 1. Attempt to invite a user with SUPER_ADMIN role -> 403 Forbidden
        invite_payload = {
            "email": f"hacker_{uuid.uuid4().hex[:6]}@example.com",
            "first_name": "Privilege",
            "last_name": "Escalation",
            "role_ids": [str(super_role.id)],
        }
        esc_resp = await client.post(
            "/api/v1/organizations/me/users",
            headers=headers,
            json=invite_payload,
        )
        assert esc_resp.status_code == 403
        assert "Privilege escalation prevented" in esc_resp.json()["detail"]

        # 2. Attempt to self-deactivate -> 400 Bad Request
        self_deact_resp = await client.patch(
            f"/api/v1/organizations/me/users/{admin_user['id']}/status",
            headers=headers,
            json={"is_active": False},
        )
        assert self_deact_resp.status_code == 400
        assert "cannot change the active status of your own account" in self_deact_resp.json()["detail"]

        # 3. Attempt to self-revoke -> 400 Bad Request
        self_del_resp = await client.delete(
            f"/api/v1/organizations/me/users/{admin_user['id']}",
            headers=headers,
        )
        assert self_del_resp.status_code == 400
        assert "cannot revoke your own account access" in self_del_resp.json()["detail"]
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_cross_tenant_idor_prevention(test_engine):
    """
    CRITICAL IDOR TEST:
    Verifies that a user from Organization A CANNOT view, modify, update roles,
    or delete a user belonging to Organization B.
    All cross-tenant requests must return 404 Not Found.
    """
    client_a, user_a, headers_a, _ = await create_user_session(test_engine, "org_a")
    client_b, user_b, headers_b, _ = await create_user_session(test_engine, "org_b")
    try:
        # Org A attempts to GET Org B's admin user details
        idor_get = await client_a.get(
            f"/api/v1/organizations/me/users/{user_b['id']}",
            headers=headers_a,
        )
        assert idor_get.status_code == 404
        assert "User not found in this organization" in idor_get.json()["detail"]

        # Org A attempts to update Org B's user status
        idor_patch = await client_a.patch(
            f"/api/v1/organizations/me/users/{user_b['id']}/status",
            headers=headers_a,
            json={"is_active": False},
        )
        assert idor_patch.status_code == 404

        # Org A attempts to update Org B's user roles
        roles_resp = await client_a.get("/api/v1/organizations/me/roles", headers=headers_a)
        any_role_id = roles_resp.json()[0]["id"]
        idor_put = await client_a.put(
            f"/api/v1/organizations/me/users/{user_b['id']}/roles",
            headers=headers_a,
            json={"role_ids": [any_role_id]},
        )
        assert idor_put.status_code == 404

        # Org A attempts to delete Org B's user
        idor_del = await client_a.delete(
            f"/api/v1/organizations/me/users/{user_b['id']}",
            headers=headers_a,
        )
        assert idor_del.status_code == 404
    finally:
        await client_a.aclose()
        await client_b.aclose()


@pytest.mark.asyncio
async def test_multi_tenant_transporter_linking(test_engine, async_db: AsyncSession):
    """
    Verifies that multiple manufacturer organizations can link to a single master Transporter
    without duplicating the Transporter entity, and unlinking from one does not impact the other.
    """
    client_a, user_a, headers_a, _ = await create_user_session(test_engine, "mfg_a")
    client_b, user_b, headers_b, _ = await create_user_session(test_engine, "mfg_b")
    try:
        # Create a shared master Transporter directly in DB
        carrier_org = Organization(
            name="Apex Freight Lines",
            slug=f"apex-freight-{uuid.uuid4().hex[:6]}",
            org_type="CARRIER",
            is_active=True,
        )
        async_db.add(carrier_org)
        await async_db.flush()

        master_transporter = Transporter(
            organization_id=carrier_org.id,
            name="Apex Freight Lines",
            code=f"APEX_{uuid.uuid4().hex[:4].upper()}",
            phone="+18005550199",
            email="dispatch@apexfreight.com",
            is_active=True,
        )
        async_db.add(master_transporter)
        await async_db.commit()
        await async_db.refresh(master_transporter)

        # 1. Mfg A links Transporter
        link_a = await client_a.post(
            "/api/v1/organizations/me/transporters/link",
            headers=headers_a,
            json={
                "transporter_id": str(master_transporter.id),
                "contract_reference": "CONTRACT-MFG-A-001",
            },
        )
        assert link_a.status_code == 200
        data_a = link_a.json()
        assert data_a["transporter_name"] == "Apex Freight Lines"
        assert data_a["contract_reference"] == "CONTRACT-MFG-A-001"

        # 2. Mfg B links the SAME Transporter
        link_b = await client_b.post(
            "/api/v1/organizations/me/transporters/link",
            headers=headers_b,
            json={
                "transporter_id": str(master_transporter.id),
                "contract_reference": "CONTRACT-MFG-B-999",
            },
        )
        assert link_b.status_code == 200
        data_b = link_b.json()
        assert data_b["transporter_name"] == "Apex Freight Lines"
        assert data_b["contract_reference"] == "CONTRACT-MFG-B-999"

        # 3. List linked transporters for Mfg A and Mfg B
        list_a = (await client_a.get("/api/v1/organizations/me/transporters", headers=headers_a)).json()
        list_b = (await client_b.get("/api/v1/organizations/me/transporters", headers=headers_b)).json()
        assert len(list_a) == 1
        assert len(list_b) == 1
        assert list_a[0]["transporter_id"] == str(master_transporter.id)
        assert list_b[0]["transporter_id"] == str(master_transporter.id)

        # 4. Mfg A unlinks Transporter
        unlink_a = await client_a.delete(
            f"/api/v1/organizations/me/transporters/{master_transporter.id}",
            headers=headers_a,
        )
        assert unlink_a.status_code == 200

        # 5. Verify Mfg A has 0 active linked transporters, but Mfg B STILL has 1 active linked transporter!
        list_a_after = (await client_a.get("/api/v1/organizations/me/transporters", headers=headers_a)).json()
        list_b_after = (await client_b.get("/api/v1/organizations/me/transporters", headers=headers_b)).json()
        assert len(list_a_after) == 0
        assert len(list_b_after) == 1
        assert list_b_after[0]["transporter_id"] == str(master_transporter.id)
    finally:
        await client_a.aclose()
        await client_b.aclose()
