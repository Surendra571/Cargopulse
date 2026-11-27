import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import generate_secure_random_token, hash_password
from app.models import (
    AuditLog,
    Organization,
    OrganizationTransporter,
    Permission,
    RefreshSession,
    Role,
    RolePermission,
    Transporter,
    User,
    UserRole,
    UserRoleType,
)
from app.schemas.organization import (
    InviteUserRequest,
    LinkTransporterRequest,
    OrganizationResponse,
    OrganizationTransporterResponse,
    OrganizationUpdateRequest,
    PermissionResponse,
    RoleResponse,
    TenantUserResponse,
)

STANDARD_PERMISSIONS = [
    # Organization & Users
    ("organization:read", "View Organization Profile", "organization", "View basic organization settings and details"),
    ("organization:manage", "Manage Organization", "organization", "Update organization profile and configuration"),
    ("organization:settings", "Manage Settings", "organization", "Update custom tenant settings and thresholds"),
    ("users:read", "View Organization Users", "users", "View user accounts and profiles within organization"),
    ("users:manage", "Manage Organization Users", "users", "Invite, update roles, activate, deactivate and revoke users"),
    ("roles:read", "View Roles & Permissions", "roles", "View available roles and permission sets"),

    # Shipments
    ("shipments:read", "View Shipments", "shipments", "Access shipment lists and basic shipment details"),
    ("shipments:create", "Create Shipments", "shipments", "Create new outbound freight shipments"),
    ("shipments:update", "Update Shipments", "shipments", "Modify eligible draft/pending shipment details"),
    ("shipments:manage", "Full Shipment Management", "shipments", "Manage, cancel, and modify any shipment"),
    ("shipment_history:read", "View Shipment History", "shipments", "View auditable shipment events and timeline"),
    ("assigned_shipments:read", "View Assigned Shipments", "shipments", "View only shipments explicitly assigned to driver"),

    # Transporters & Fleet
    ("transporters:read", "View Transporters", "transporters", "View carrier directory and linked transporters"),
    ("transporters:manage", "Manage Transporters", "transporters", "Link, unlink, and manage transporter relationships"),
    ("transporters:match", "Match Transporters", "transporters", "Run matching engine and suggest transporters"),
    ("transporter_profile:read", "View Carrier Profile", "transporters", "View carrier company profile"),
    ("transporter_profile:manage", "Manage Carrier Profile", "transporters", "Update carrier profile and configurations"),
    ("fleet:read", "View Fleet", "transporters", "View vehicles and drivers"),
    ("fleet:manage", "Manage Fleet", "transporters", "Register, update, and manage vehicles and drivers"),

    # Bookings & Commitments
    ("bookings:create", "Create Bookings", "dispatch", "Create and dispatch booking requests to transporters"),
    ("bookings:read", "View Bookings", "dispatch", "View booking requests and status"),
    ("bookings:respond", "Accept/Reject Bookings", "dispatch", "Accept or reject booking dispatch requests"),
    ("commitments:manage", "Manage Commitments", "dispatch", "Confirm pickup commitments and SLA targets"),
    ("commitments:read", "Monitor Pickups", "dispatch", "Monitor pickup commitments and execution"),

    # Execution & Milestones
    ("shipment_arrival:record", "Record Pickup Arrival", "execution", "Record driver arrival at pickup facility"),
    ("shipment_pickup:confirm", "Confirm Pickup", "execution", "Confirm freight loading and departure"),
    ("shipment_delivery:submit", "Submit Delivery", "execution", "Record delivery arrival and unloading"),
    ("milestones:submit", "Submit Milestones", "execution", "Submit transit milestone telemetry and status"),
    ("pod:upload", "Upload POD Evidence", "execution", "Upload physical proof of delivery documents"),
    ("pod:verify", "Verify Proof of Delivery", "operations", "Audit and verify POD signatures and photos"),
    ("pod:read", "View Proof of Delivery", "operations", "View POD documents and verification status"),

    # Exceptions & Operations
    ("exceptions:manage", "Manage Exceptions", "operations", "Create and manage operational exceptions"),
    ("exceptions:read", "View Exceptions", "operations", "View operational exceptions and incidents"),
    ("recovery:manage", "Manage Recovery", "operations", "Initiate and approve shipment recovery actions"),
    ("reconciliation:manage", "Manage Reconciliation", "operations", "Manage billing disputes and reconciliation"),

    # Analytics & Audit
    ("analytics:read", "View Analytics", "analytics", "Access operational performance dashboards and KPIs"),
    ("audit:read", "View Audit Trail", "audit", "Inspect immutable compliance audit logs"),
    ("admin:all", "Full Organization Administration", "admin", "Unrestricted administrator control over tenant resources"),
]

ROLE_TEMPLATES = {
    UserRoleType.ORGANIZATION_ADMIN: {
        "name": "Organization Administrator",
        "description": "Full administrative access across tenant resources, users, and transporters",
        "is_system_role": True,
        "permissions": [
            "organization:read", "organization:manage", "organization:settings",
            "users:read", "users:manage", "roles:read",
            "shipments:read", "shipments:create", "shipments:update", "shipments:manage", "shipment_history:read",
            "transporters:read", "transporters:manage", "transporters:match",
            "bookings:create", "bookings:read", "commitments:manage", "commitments:read",
            "exceptions:manage", "exceptions:read", "recovery:manage",
            "pod:verify", "pod:read",
            "reconciliation:manage",
            "analytics:read", "audit:read",
            "admin:all",
        ],
    },
    UserRoleType.DISPATCH_MANAGER: {
        "name": "Dispatch Manager",
        "description": "Manages outbound shipments, transporter matching, dispatch bookings, and commitments",
        "is_system_role": True,
        "permissions": [
            "organization:read",
            "shipments:read", "shipments:create", "shipments:update", "shipment_history:read",
            "transporters:read", "transporters:match",
            "bookings:create", "bookings:read",
            "commitments:manage", "commitments:read",
            "pod:read",
        ],
    },
    UserRoleType.OPERATIONS_MANAGER: {
        "name": "Operations Manager",
        "description": "Monitors in-transit freight, manages pickup SLA compliance, exceptions, and recovery",
        "is_system_role": True,
        "permissions": [
            "organization:read",
            "shipments:read", "shipment_history:read",
            "commitments:read",
            "exceptions:manage", "exceptions:read",
            "recovery:manage",
            "pod:read", "pod:verify",
            "reconciliation:manage",
            "analytics:read",
        ],
    },
    UserRoleType.TRANSPORTER_ADMIN: {
        "name": "Transporter Administrator",
        "description": "Manages carrier fleet, driver roster, booking acceptances, and milestone dispatches",
        "is_system_role": True,
        "permissions": [
            "organization:read",
            "transporter_profile:read", "transporter_profile:manage",
            "fleet:read", "fleet:manage",
            "bookings:read", "bookings:respond",
            "milestones:submit",
            "pod:read",
        ],
    },
    UserRoleType.DRIVER: {
        "name": "Driver",
        "description": "Executes assigned shipments, records arrival, departure, deliveries, and uploads POD evidence",
        "is_system_role": True,
        "permissions": [
            "assigned_shipments:read",
            "shipment_arrival:record",
            "shipment_pickup:confirm",
            "shipment_delivery:submit",
            "pod:upload",
        ],
    },
}


class OrganizationService:
    """Multi-tenant organization management, tenant isolation, and RBAC service."""

    @classmethod
    async def ensure_standard_roles_and_permissions(
        cls, session: AsyncSession, org_id: Optional[uuid.UUID] = None
    ) -> None:
        """
        Seeds standard permissions if missing and provisions standard roles
        for the given organization (or system-wide if org_id is None).
        """
        # 1. Upsert permissions
        perm_map: Dict[str, Permission] = {}
        for code, name, module, desc in STANDARD_PERMISSIONS:
            stmt = select(Permission).where(Permission.code == code)
            perm = (await session.execute(stmt)).scalar_one_or_none()
            if not perm:
                perm = Permission(code=code, name=name, module=module, description=desc)
                session.add(perm)
                await session.flush()
            perm_map[code] = perm

        # 2. If org_id is provided, provision standard roles for this tenant
        if org_id:
            for role_type, template in ROLE_TEMPLATES.items():
                stmt = select(Role).where(
                    Role.organization_id == org_id,
                    Role.role_type == role_type,
                )
                role = (await session.execute(stmt)).scalar_one_or_none()
                if not role:
                    role = Role(
                        organization_id=org_id,
                        name=template["name"],
                        role_type=role_type,
                        description=template["description"],
                        is_system_role=template["is_system_role"],
                    )
                    session.add(role)
                    await session.flush()

                # Ensure role_permissions
                existing_perms_stmt = select(RolePermission.permission_id).where(
                    RolePermission.role_id == role.id
                )
                existing_pids = set((await session.execute(existing_perms_stmt)).scalars().all())

                for code in template["permissions"]:
                    p_obj = perm_map.get(code)
                    if p_obj and p_obj.id not in existing_pids:
                        rp = RolePermission(role_id=role.id, permission_id=p_obj.id)
                        session.add(rp)
            await session.flush()

    @classmethod
    async def get_organization(
        cls, session: AsyncSession, org_id: uuid.UUID
    ) -> OrganizationResponse:
        """Fetches an organization ensuring isolation."""
        stmt = select(Organization).where(
            Organization.id == org_id, Organization.is_deleted == False  # noqa: E712
        )
        org = (await session.execute(stmt)).scalar_one_or_none()
        if not org:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found.",
            )
        return OrganizationResponse.model_validate(org)

    @classmethod
    async def update_organization(
        cls,
        session: AsyncSession,
        org_id: uuid.UUID,
        payload: OrganizationUpdateRequest,
        current_user: User,
    ) -> OrganizationResponse:
        """Updates organization profile with tenant isolation and audit logging."""
        stmt = select(Organization).where(
            Organization.id == org_id, Organization.is_deleted == False  # noqa: E712
        )
        org = (await session.execute(stmt)).scalar_one_or_none()
        if not org:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found.",
            )

        changes: Dict[str, Any] = {}
        if payload.name is not None and payload.name != org.name:
            changes["name"] = {"old": org.name, "new": payload.name}
            org.name = payload.name
        if payload.billing_email is not None and payload.billing_email != org.billing_email:
            changes["billing_email"] = {"old": org.billing_email, "new": payload.billing_email}
            org.billing_email = payload.billing_email
        if payload.tax_identifier is not None and payload.tax_identifier != org.tax_identifier:
            changes["tax_identifier"] = {"old": org.tax_identifier, "new": payload.tax_identifier}
            org.tax_identifier = payload.tax_identifier

        if changes:
            audit = AuditLog(
                organization_id=org_id,
                user_id=current_user.id,
                entity_name="Organization",
                entity_id=org_id,
                action="UPDATE_PROFILE",
                changes=changes,
            )
            session.add(audit)
            await session.commit()
            await session.refresh(org)

        return OrganizationResponse.model_validate(org)

    @classmethod
    async def get_settings(
        cls, session: AsyncSession, org_id: uuid.UUID
    ) -> Dict[str, Any]:
        """Retrieves organization configuration settings."""
        stmt = select(Organization.settings).where(
            Organization.id == org_id, Organization.is_deleted == False  # noqa: E712
        )
        settings = (await session.execute(stmt)).scalar_one_or_none()
        return settings if settings is not None else {}

    @classmethod
    async def update_settings(
        cls,
        session: AsyncSession,
        org_id: uuid.UUID,
        new_settings: Dict[str, Any],
        current_user: User,
    ) -> Dict[str, Any]:
        """Merges or updates organization configuration settings."""
        stmt = select(Organization).where(
            Organization.id == org_id, Organization.is_deleted == False  # noqa: E712
        )
        org = (await session.execute(stmt)).scalar_one_or_none()
        if not org:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found.",
            )

        merged_settings = dict(org.settings or {})
        merged_settings.update(new_settings)

        audit = AuditLog(
            organization_id=org_id,
            user_id=current_user.id,
            entity_name="Organization",
            entity_id=org_id,
            action="UPDATE_SETTINGS",
            changes={"old_settings": org.settings, "new_settings": merged_settings},
        )
        org.settings = merged_settings
        session.add(audit)
        await session.commit()
        await session.refresh(org)
        return org.settings

    @classmethod
    async def list_tenant_users(
        cls,
        session: AsyncSession,
        org_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100,
        search: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> List[TenantUserResponse]:
        """Lists users within the tenant boundary with role details."""
        stmt = (
            select(User)
            .options(
                selectinload(User.user_roles).selectinload(UserRole.role)
            )
            .where(
                User.organization_id == org_id,
                User.is_deleted == False,  # noqa: E712
            )
            .order_by(User.created_at.desc())
        )

        if is_active is not None:
            stmt = stmt.where(User.is_active == is_active)

        if search:
            search_pattern = f"%{search.strip().lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(User.email).like(search_pattern),
                    func.lower(User.first_name).like(search_pattern),
                    func.lower(User.last_name).like(search_pattern),
                )
            )

        stmt = stmt.offset(skip).limit(limit)
        users = (await session.execute(stmt)).scalars().all()

        responses = []
        for u in users:
            role_names = [ur.role.name for ur in u.user_roles if ur.role]
            role_ids = [ur.role_id for ur in u.user_roles]
            responses.append(
                TenantUserResponse(
                    id=u.id,
                    email=u.email,
                    first_name=u.first_name,
                    last_name=u.last_name,
                    phone=u.phone,
                    is_active=u.is_active,
                    is_superadmin=u.is_superadmin,
                    roles=role_names,
                    role_ids=role_ids,
                    created_at=u.created_at,
                    last_login_at=u.last_login_at,
                )
            )
        return responses

    @classmethod
    async def get_tenant_user(
        cls, session: AsyncSession, org_id: uuid.UUID, user_id: uuid.UUID
    ) -> TenantUserResponse:
        """
        Retrieves a user account strictly bounded to the tenant organization.
        Raises 404 if user belongs to another organization (preventing IDOR).
        """
        stmt = (
            select(User)
            .options(
                selectinload(User.user_roles).selectinload(UserRole.role)
            )
            .where(
                User.id == user_id,
                User.organization_id == org_id,
                User.is_deleted == False,  # noqa: E712
            )
        )
        user = (await session.execute(stmt)).scalar_one_or_none()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found in this organization.",
            )

        role_names = [ur.role.name for ur in user.user_roles if ur.role]
        role_ids = [ur.role_id for ur in user.user_roles]

        return TenantUserResponse(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            phone=user.phone,
            is_active=user.is_active,
            is_superadmin=user.is_superadmin,
            roles=role_names,
            role_ids=role_ids,
            created_at=user.created_at,
            last_login_at=user.last_login_at,
        )

    @classmethod
    async def invite_or_create_user(
        cls,
        session: AsyncSession,
        org_id: uuid.UUID,
        payload: InviteUserRequest,
        current_user: User,
    ) -> TenantUserResponse:
        """
        Creates/invites a user inside the organization.
        Enforces tenant scoping, prevents duplicate accounts, and blocks privilege escalation.
        """
        email_clean = payload.email.lower().strip()

        # Check for duplicate email in this organization
        existing_stmt = select(User).where(
            User.organization_id == org_id,
            User.email == email_clean,
            User.is_deleted == False,  # noqa: E712
        )
        existing = (await session.execute(existing_stmt)).scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this email address already exists in your organization.",
            )

        # Validate requested roles belong to this tenant or are system roles
        roles_stmt = select(Role).where(
            Role.id.in_(payload.role_ids),
            or_(Role.organization_id == org_id, Role.is_system_role == True),  # noqa: E712
        )
        valid_roles = (await session.execute(roles_stmt)).scalars().all()
        if len(valid_roles) != len(set(payload.role_ids)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One or more specified roles are invalid or not available in this organization.",
            )

        # Privilege escalation check: non-superadmin cannot assign SUPER_ADMIN
        for r in valid_roles:
            if (r.role_type == UserRoleType.SUPER_ADMIN or r.name.upper() == "SUPER_ADMIN") and not current_user.is_superadmin:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Privilege escalation prevented: only superadmins can assign the SUPER_ADMIN role.",
                )

        password = payload.initial_password or generate_secure_random_token(16)
        new_user = User(
            organization_id=org_id,
            email=email_clean,
            first_name=payload.first_name.strip(),
            last_name=payload.last_name.strip(),
            phone=payload.phone.strip() if payload.phone else None,
            hashed_password=hash_password(password),
            is_active=True,
            is_superadmin=False,
        )
        session.add(new_user)
        await session.flush()

        for r in valid_roles:
            ur = UserRole(user_id=new_user.id, role_id=r.id, role=r)
            session.add(ur)

        audit = AuditLog(
            organization_id=org_id,
            user_id=current_user.id,
            entity_name="User",
            entity_id=new_user.id,
            action="INVITE_USER",
            changes={
                "email": email_clean,
                "first_name": new_user.first_name,
                "last_name": new_user.last_name,
                "roles": [r.name for r in valid_roles],
            },
        )
        session.add(audit)
        await session.commit()

        return TenantUserResponse(
            id=new_user.id,
            email=new_user.email,
            first_name=new_user.first_name,
            last_name=new_user.last_name,
            phone=new_user.phone,
            is_active=new_user.is_active,
            is_superadmin=new_user.is_superadmin,
            roles=[r.name for r in valid_roles],
            role_ids=[r.id for r in valid_roles],
            created_at=new_user.created_at,
            last_login_at=new_user.last_login_at,
        )

    @classmethod
    async def update_user_roles(
        cls,
        session: AsyncSession,
        org_id: uuid.UUID,
        target_user_id: uuid.UUID,
        role_ids: List[uuid.UUID],
        current_user: User,
    ) -> TenantUserResponse:
        """
        Updates roles assigned to a user within tenant scope.
        Prevents privilege escalation and cross-tenant tampering.
        """
        stmt = (
            select(User)
            .options(selectinload(User.user_roles))
            .where(
                User.id == target_user_id,
                User.organization_id == org_id,
                User.is_deleted == False,  # noqa: E712
            )
        )
        target_user = (await session.execute(stmt)).scalar_one_or_none()
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found in this organization.",
            )

        if target_user.is_superadmin and not current_user.is_superadmin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only superadmins can modify roles for a superadmin user.",
            )

        # Validate requested roles belong to this tenant or are system roles
        roles_stmt = select(Role).where(
            Role.id.in_(role_ids),
            or_(Role.organization_id == org_id, Role.is_system_role == True),  # noqa: E712
        )
        valid_roles = (await session.execute(roles_stmt)).scalars().all()
        if len(valid_roles) != len(set(role_ids)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One or more specified roles are invalid or not available in this organization.",
            )

        # Privilege escalation check
        for r in valid_roles:
            if (r.role_type == UserRoleType.SUPER_ADMIN or r.name.upper() == "SUPER_ADMIN") and not current_user.is_superadmin:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Privilege escalation prevented: only superadmins can assign the SUPER_ADMIN role.",
                )

        # Delete existing user roles and assign new roles
        del_stmt = delete(UserRole).where(UserRole.user_id == target_user.id)
        await session.execute(del_stmt)

        for r in valid_roles:
            ur = UserRole(user_id=target_user.id, role_id=r.id)
            session.add(ur)

        audit = AuditLog(
            organization_id=org_id,
            user_id=current_user.id,
            entity_name="User",
            entity_id=target_user.id,
            action="UPDATE_ROLES",
            changes={"new_roles": [r.name for r in valid_roles]},
        )
        session.add(audit)
        await session.commit()

        return TenantUserResponse(
            id=target_user.id,
            email=target_user.email,
            first_name=target_user.first_name,
            last_name=target_user.last_name,
            phone=target_user.phone,
            is_active=target_user.is_active,
            is_superadmin=target_user.is_superadmin,
            roles=[r.name for r in valid_roles],
            role_ids=[r.id for r in valid_roles],
            created_at=target_user.created_at,
            last_login_at=target_user.last_login_at,
        )

    @classmethod
    async def update_user_status(
        cls,
        session: AsyncSession,
        org_id: uuid.UUID,
        target_user_id: uuid.UUID,
        is_active: bool,
        current_user: User,
    ) -> TenantUserResponse:
        """
        Activates or deactivates a user account.
        When deactivating: IMMEDIATELY revokes all active refresh sessions to kill session access.
        """
        if target_user_id == current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot change the active status of your own account.",
            )

        stmt = (
            select(User)
            .options(selectinload(User.user_roles).selectinload(UserRole.role))
            .where(
                User.id == target_user_id,
                User.organization_id == org_id,
                User.is_deleted == False,  # noqa: E712
            )
        )
        target_user = (await session.execute(stmt)).scalar_one_or_none()
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found in this organization.",
            )

        if target_user.is_superadmin and not current_user.is_superadmin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only superadmins can deactivate a superadmin account.",
            )

        target_user.is_active = is_active

        # If deactivating, immediately revoke all active refresh sessions
        if not is_active:
            now_utc = datetime.now(timezone.utc)
            revoke_sessions_stmt = (
                update(RefreshSession)
                .where(
                    RefreshSession.user_id == target_user_id,
                    RefreshSession.revoked_at.is_(None),
                )
                .values(revoked_at=now_utc)
            )
            await session.execute(revoke_sessions_stmt)

        audit = AuditLog(
            organization_id=org_id,
            user_id=current_user.id,
            entity_name="User",
            entity_id=target_user.id,
            action="ACTIVATE_USER" if is_active else "DEACTIVATE_USER",
            changes={"is_active": {"new": is_active}},
        )
        session.add(audit)
        await session.commit()

        role_names = [ur.role.name for ur in target_user.user_roles if ur.role]
        role_ids = [ur.role_id for ur in target_user.user_roles]

        return TenantUserResponse(
            id=target_user.id,
            email=target_user.email,
            first_name=target_user.first_name,
            last_name=target_user.last_name,
            phone=target_user.phone,
            is_active=target_user.is_active,
            is_superadmin=target_user.is_superadmin,
            roles=role_names,
            role_ids=role_ids,
            created_at=target_user.created_at,
            last_login_at=target_user.last_login_at,
        )

    @classmethod
    async def revoke_user_access(
        cls,
        session: AsyncSession,
        org_id: uuid.UUID,
        target_user_id: uuid.UUID,
        current_user: User,
    ) -> None:
        """
        Revokes user access permanently (soft-delete + immediate session revocation).
        Prevents IDOR and self-revocation.
        """
        if target_user_id == current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot revoke your own account access.",
            )

        stmt = select(User).where(
            User.id == target_user_id,
            User.organization_id == org_id,
            User.is_deleted == False,  # noqa: E712
        )
        target_user = (await session.execute(stmt)).scalar_one_or_none()
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found in this organization.",
            )

        if target_user.is_superadmin and not current_user.is_superadmin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only superadmins can revoke access for a superadmin user.",
            )

        now_utc = datetime.now(timezone.utc)
        target_user.is_deleted = True
        target_user.deleted_at = now_utc
        target_user.is_active = False

        # Invalidate all active refresh sessions immediately
        revoke_sessions_stmt = (
            update(RefreshSession)
            .where(
                RefreshSession.user_id == target_user_id,
                RefreshSession.revoked_at.is_(None),
            )
            .values(revoked_at=now_utc)
        )
        await session.execute(revoke_sessions_stmt)

        audit = AuditLog(
            organization_id=org_id,
            user_id=current_user.id,
            entity_name="User",
            entity_id=target_user.id,
            action="REVOKE_USER_ACCESS",
            changes={"is_deleted": True, "revoked_at": now_utc.isoformat()},
        )
        session.add(audit)
        await session.commit()

    @classmethod
    async def list_roles(
        cls, session: AsyncSession, org_id: uuid.UUID, current_user: User
    ) -> List[RoleResponse]:
        """Lists roles available to this organization, including standard system roles."""
        stmt = (
            select(Role)
            .options(
                selectinload(Role.role_permissions).selectinload(RolePermission.permission)
            )
            .where(
                or_(Role.organization_id == org_id, Role.is_system_role == True)  # noqa: E712
            )
            .order_by(Role.name.asc())
        )
        roles = (await session.execute(stmt)).scalars().all()

        role_responses = []
        for r in roles:
            # Exclude SUPER_ADMIN role for non-superadmins
            if (r.role_type == UserRoleType.SUPER_ADMIN or r.name.upper() == "SUPER_ADMIN") and not current_user.is_superadmin:
                continue

            perms = [
                PermissionResponse.model_validate(rp.permission)
                for rp in r.role_permissions
                if rp.permission
            ]
            role_responses.append(
                RoleResponse(
                    id=r.id,
                    name=r.name,
                    role_type=r.role_type,
                    description=r.description,
                    is_system_role=r.is_system_role,
                    permissions=perms,
                )
            )
        return role_responses

    @classmethod
    async def list_permissions(cls, session: AsyncSession) -> List[PermissionResponse]:
        """Lists all registered platform permissions."""
        stmt = select(Permission).order_by(Permission.module.asc(), Permission.code.asc())
        perms = (await session.execute(stmt)).scalars().all()
        return [PermissionResponse.model_validate(p) for p in perms]

    # Transporter multi-tenant association
    @classmethod
    async def link_transporter(
        cls,
        session: AsyncSession,
        org_id: uuid.UUID,
        payload: LinkTransporterRequest,
        current_user: User,
    ) -> OrganizationTransporterResponse:
        """
        Associates an existing master transporter with the tenant organization.
        Enables cross-manufacturer carrier sharing without duplicating carrier fleet or driver records.
        """
        # Ensure transporter exists
        t_stmt = select(Transporter).where(
            Transporter.id == payload.transporter_id,
            Transporter.is_deleted == False,  # noqa: E712
        )
        transporter = (await session.execute(t_stmt)).scalar_one_or_none()
        if not transporter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transporter not found.",
            )

        # Check if already linked
        existing_stmt = select(OrganizationTransporter).where(
            OrganizationTransporter.organization_id == org_id,
            OrganizationTransporter.transporter_id == payload.transporter_id,
        )
        existing = (await session.execute(existing_stmt)).scalar_one_or_none()
        if existing:
            if existing.status != "ACTIVE":
                existing.status = "ACTIVE"
                existing.contract_reference = payload.contract_reference or existing.contract_reference
                existing.custom_rates = payload.custom_rates or existing.custom_rates
                await session.commit()
                await session.refresh(existing)
            return OrganizationTransporterResponse(
                id=existing.id,
                organization_id=existing.organization_id,
                transporter_id=transporter.id,
                transporter_name=transporter.name,
                transporter_code=transporter.code,
                status=existing.status,
                contract_reference=existing.contract_reference,
                custom_rates=existing.custom_rates,
                created_at=existing.created_at,
            )

        link = OrganizationTransporter(
            organization_id=org_id,
            transporter_id=payload.transporter_id,
            status="ACTIVE",
            contract_reference=payload.contract_reference,
            custom_rates=payload.custom_rates or {},
        )
        session.add(link)

        audit = AuditLog(
            organization_id=org_id,
            user_id=current_user.id,
            entity_name="OrganizationTransporter",
            entity_id=payload.transporter_id,
            action="LINK_TRANSPORTER",
            changes={
                "transporter_name": transporter.name,
                "contract_reference": payload.contract_reference,
            },
        )
        session.add(audit)
        await session.commit()
        await session.refresh(link)

        return OrganizationTransporterResponse(
            id=link.id,
            organization_id=link.organization_id,
            transporter_id=transporter.id,
            transporter_name=transporter.name,
            transporter_code=transporter.code,
            status=link.status,
            contract_reference=link.contract_reference,
            custom_rates=link.custom_rates,
            created_at=link.created_at,
        )

    @classmethod
    async def list_linked_transporters(
        cls, session: AsyncSession, org_id: uuid.UUID
    ) -> List[OrganizationTransporterResponse]:
        """Lists all transporters linked to the tenant organization."""
        stmt = (
            select(OrganizationTransporter)
            .options(selectinload(OrganizationTransporter.transporter))
            .where(
                OrganizationTransporter.organization_id == org_id,
                OrganizationTransporter.status == "ACTIVE",
            )
            .order_by(OrganizationTransporter.created_at.desc())
        )
        links = (await session.execute(stmt)).scalars().all()

        responses = []
        for l in links:
            if l.transporter and not l.transporter.is_deleted:
                responses.append(
                    OrganizationTransporterResponse(
                        id=l.id,
                        organization_id=l.organization_id,
                        transporter_id=l.transporter.id,
                        transporter_name=l.transporter.name,
                        transporter_code=l.transporter.code,
                        status=l.status,
                        contract_reference=l.contract_reference,
                        custom_rates=l.custom_rates,
                        created_at=l.created_at,
                    )
                )
        return responses

    @classmethod
    async def unlink_transporter(
        cls,
        session: AsyncSession,
        org_id: uuid.UUID,
        transporter_id: uuid.UUID,
        current_user: User,
    ) -> None:
        """Unlinks / terminates transporter association for this tenant."""
        stmt = select(OrganizationTransporter).where(
            OrganizationTransporter.organization_id == org_id,
            OrganizationTransporter.transporter_id == transporter_id,
        )
        link = (await session.execute(stmt)).scalar_one_or_none()
        if not link:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transporter association not found for this organization.",
            )

        link.status = "SUSPENDED"
        audit = AuditLog(
            organization_id=org_id,
            user_id=current_user.id,
            entity_name="OrganizationTransporter",
            entity_id=transporter_id,
            action="UNLINK_TRANSPORTER",
            changes={"status": "SUSPENDED"},
        )
        session.add(audit)
        await session.commit()
