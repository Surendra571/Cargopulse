import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.security import (
    create_access_token,
    generate_secure_random_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.models import (
    AuditLog,
    Organization,
    OrganizationType,
    PasswordResetToken,
    Permission,
    RefreshSession,
    Role,
    RolePermission,
    User,
    UserRole,
    UserRoleType,
)
from app.schemas.auth import RegisterRequest, UserProfileResponse


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return slug or "org"


class AuthService:
    """Core authentication, session management, and authorization service."""

    @staticmethod
    async def get_user_with_relations(session: AsyncSession, user_id: uuid.UUID) -> Optional[User]:
        """Loads a user with their organization, user_roles, roles, and permissions."""
        stmt = (
            select(User)
            .options(
                selectinload(User.organization),
                selectinload(User.user_roles)
                .selectinload(UserRole.role)
                .selectinload(Role.role_permissions)
                .selectinload(RolePermission.permission),
            )
            .where(User.id == user_id, User.is_deleted == False)  # noqa: E712
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    def extract_roles_and_permissions(user: User) -> Tuple[List[str], List[str]]:
        """Extracts list of role names and permission codes from loaded user relations."""
        roles = []
        permissions_set = set()

        for ur in user.user_roles:
            if ur.role:
                roles.append(ur.role.name)
                if ur.role.role_type == UserRoleType.ORGANIZATION_ADMIN and "Administrator" not in roles:
                    roles.append("Administrator")
                for rp in ur.role.role_permissions:
                    if rp.permission and rp.permission.code:
                        permissions_set.add(rp.permission.code)

        # Default system fallback if role has no permissions
        if user.is_superadmin:
            permissions_set.add("*:*")

        return roles, sorted(list(permissions_set))

    @classmethod
    def serialize_profile(cls, user: User) -> UserProfileResponse:
        """Serializes user model to UserProfileResponse."""
        roles, permissions = cls.extract_roles_and_permissions(user)
        return UserProfileResponse(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            phone=user.phone,
            is_active=user.is_active,
            is_superadmin=user.is_superadmin,
            organization_id=user.organization_id,
            organization_name=user.organization.name if user.organization else "",
            organization_slug=user.organization.slug if user.organization else "",
            organization_type=user.organization.org_type if user.organization else OrganizationType.MANUFACTURER,
            roles=roles,
            permissions=permissions,
        )

    @classmethod
    async def register_organization_and_admin(
        cls,
        session: AsyncSession,
        payload: RegisterRequest,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Tuple[User, str, str]:
        """
        Atomically creates:
        1. Tenant organization
        2. System permissions & Administrator role
        3. Initial administrator user with Argon2id hashed password
        4. UserRole assignment
        5. Audit log entry
        Returns (user, access_token, raw_refresh_token).
        """
        email_clean = payload.email.lower().strip()

        # Check if email is already taken in the system by an existing admin to avoid duplicate accounts
        existing_user_stmt = select(User).where(User.email == email_clean, User.is_deleted == False)  # noqa: E712
        existing_user = (await session.execute(existing_user_stmt)).scalar_one_or_none()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this work email already exists.",
            )

        # Generate unique organization slug
        base_slug = _slugify(payload.organization_name)
        slug = base_slug
        slug_check_stmt = select(Organization).where(Organization.slug == slug)
        existing_org = (await session.execute(slug_check_stmt)).scalar_one_or_none()
        if existing_org:
            slug = f"{base_slug}-{uuid.uuid4().hex[:6]}"

        # 1. Create Organization
        org = Organization(
            name=payload.organization_name.strip(),
            slug=slug,
            org_type=payload.org_type,
            is_active=True,
            billing_email=email_clean,
            settings={"terms_accepted_at": datetime.now(timezone.utc).isoformat()},
        )
        session.add(org)
        await session.flush()

        # 2. Seed standard roles and permissions for this tenant
        from app.services.organization_service import OrganizationService
        await OrganizationService.ensure_standard_roles_and_permissions(session, org.id)

        # 3. Locate the ORGANIZATION_ADMIN role for this tenant
        admin_role_stmt = select(Role).where(
            Role.organization_id == org.id,
            Role.role_type == UserRoleType.ORGANIZATION_ADMIN,
        )
        admin_role = (await session.execute(admin_role_stmt)).scalar_one()

        # 4. Create Administrator User
        name_parts = payload.full_name.strip().split(" ", 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        user = User(
            organization_id=org.id,
            email=email_clean,
            hashed_password=hash_password(payload.password),
            first_name=first_name,
            last_name=last_name,
            is_active=True,
            is_superadmin=False,
            last_login_at=datetime.now(timezone.utc),
        )
        session.add(user)
        await session.flush()

        # 5. Assign Administrator Role to User
        user_role = UserRole(user_id=user.id, role_id=admin_role.id)
        session.add(user_role)

        # 7. Audit Log
        audit = AuditLog(
            organization_id=org.id,
            user_id=user.id,
            action="ORGANIZATION_REGISTERED",
            entity_name="organizations",
            entity_id=org.id,
            ip_address=ip_address,
            user_agent=user_agent,
            changes={"organization_name": org.name, "slug": org.slug, "admin_email": user.email},
        )
        session.add(audit)

        # 8. Create Refresh Session
        raw_refresh_token = generate_secure_random_token(64)
        refresh_session = RefreshSession(
            user_id=user.id,
            token_hash=hash_token(raw_refresh_token),
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            user_agent=user_agent,
            ip_address=ip_address,
        )
        session.add(refresh_session)

        await session.commit()

        # Reload user with relations
        loaded_user = await cls.get_user_with_relations(session, user.id)
        if not loaded_user:
            raise HTTPException(status_code=500, detail="Failed to initialize user session")

        roles, permissions = cls.extract_roles_and_permissions(loaded_user)
        access_token = create_access_token(
            subject=str(loaded_user.id),
            organization_id=str(loaded_user.organization_id),
            roles=roles,
            permissions=permissions,
        )

        return loaded_user, access_token, raw_refresh_token

    @classmethod
    async def authenticate_user(
        cls,
        session: AsyncSession,
        email: str,
        password: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Tuple[User, str, str]:
        """
        Validates email/password credentials, checks account status, and issues session.
        Returns (user, access_token, raw_refresh_token).
        """
        email_clean = email.lower().strip()

        stmt = (
            select(User)
            .options(
                selectinload(User.organization),
                selectinload(User.user_roles)
                .selectinload(UserRole.role)
                .selectinload(Role.role_permissions)
                .selectinload(RolePermission.permission),
            )
            .where(User.email == email_clean, User.is_deleted == False)  # noqa: E712
        )
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user or not verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid work email or password.",
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your user account has been deactivated. Please contact your administrator.",
            )

        if user.organization and not user.organization.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your organization account is currently inactive.",
            )

        # Update last login
        user.last_login_at = datetime.now(timezone.utc)

        # Create refresh session
        raw_refresh_token = generate_secure_random_token(64)
        refresh_session = RefreshSession(
            user_id=user.id,
            token_hash=hash_token(raw_refresh_token),
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            user_agent=user_agent,
            ip_address=ip_address,
        )
        session.add(refresh_session)

        # Audit login
        audit = AuditLog(
            organization_id=user.organization_id,
            user_id=user.id,
            action="USER_LOGIN",
            entity_name="users",
            entity_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            changes={"email": user.email},
        )
        session.add(audit)

        await session.commit()

        roles, permissions = cls.extract_roles_and_permissions(user)
        access_token = create_access_token(
            subject=str(user.id),
            organization_id=str(user.organization_id),
            roles=roles,
            permissions=permissions,
        )

        return user, access_token, raw_refresh_token

    @classmethod
    async def rotate_refresh_token(
        cls,
        session: AsyncSession,
        raw_refresh_token: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Tuple[User, str, str]:
        """
        Executes refresh token rotation:
        1. Hashes incoming token and looks up refresh session.
        2. Detects reused/revoked tokens (security breach detection) -> terminates all sessions.
        3. Detects expired sessions.
        4. Revokes previous token and creates new session.
        Returns (user, new_access_token, new_raw_refresh_token).
        """
        token_hash = hash_token(raw_refresh_token)

        stmt = select(RefreshSession).where(RefreshSession.token_hash == token_hash)
        ref_session = (await session.execute(stmt)).scalar_one_or_none()

        if not ref_session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or unrecognized refresh session.",
            )

        # Reuse of revoked token detection
        if ref_session.revoked_at is not None:
            # Breach detected: Revoke all active sessions for this user
            await session.execute(
                update(RefreshSession)
                .where(
                    RefreshSession.user_id == ref_session.user_id,
                    RefreshSession.revoked_at.is_(None),
                )
                .values(revoked_at=datetime.now(timezone.utc))
            )
            await session.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session has been revoked. Security alert: Please log in again.",
            )

        # Check expiration
        if ref_session.expires_at < datetime.now(timezone.utc):
            ref_session.revoked_at = datetime.now(timezone.utc)
            await session.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh session has expired. Please log in again.",
            )

        # Invalidate current session (rotation)
        ref_session.revoked_at = datetime.now(timezone.utc)

        # Issue new refresh token
        new_raw_refresh_token = generate_secure_random_token(64)
        new_session = RefreshSession(
            user_id=ref_session.user_id,
            token_hash=hash_token(new_raw_refresh_token),
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            user_agent=user_agent,
            ip_address=ip_address,
        )
        session.add(new_session)

        # Fetch active user
        user = await cls.get_user_with_relations(session, ref_session.user_id)
        if not user or not user.is_active:
            await session.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is inactive or not found.",
            )

        await session.commit()

        roles, permissions = cls.extract_roles_and_permissions(user)
        new_access_token = create_access_token(
            subject=str(user.id),
            organization_id=str(user.organization_id),
            roles=roles,
            permissions=permissions,
        )

        return user, new_access_token, new_raw_refresh_token

    @classmethod
    async def revoke_session(cls, session: AsyncSession, raw_refresh_token: Optional[str]) -> None:
        """Revokes a single active refresh token session."""
        if not raw_refresh_token:
            return

        token_hash = hash_token(raw_refresh_token)
        stmt = (
            select(RefreshSession)
            .options(selectinload(RefreshSession.user))
            .where(RefreshSession.token_hash == token_hash)
        )
        ref_session = (await session.execute(stmt)).scalar_one_or_none()
        if ref_session and ref_session.revoked_at is None:
            ref_session.revoked_at = datetime.now(timezone.utc)
            # Log logout audit event
            from app.models.integrations import AuditLog
            audit_log = AuditLog(
                organization_id=ref_session.user.organization_id if ref_session.user else None,
                user_id=ref_session.user_id,
                action="USER_LOGOUT",
                entity_name="users",
                entity_id=ref_session.user_id,
                resource_type="User",
                resource_id=ref_session.user_id,
                ip_address=ref_session.ip_address,
                user_agent=ref_session.user_agent,
                changes={"session_id": str(ref_session.id)},
            )
            if audit_log.organization_id:
                session.add(audit_log)
            await session.commit()

    @classmethod
    async def request_password_reset(cls, session: AsyncSession, email: str) -> Optional[str]:
        """
        Creates a password reset token.
        Always returns success semantics externally to prevent email enumeration.
        Returns the raw token string internally (for tests/emailing) or None if user not found.
        """
        email_clean = email.lower().strip()
        stmt = select(User).where(User.email == email_clean, User.is_deleted == False)  # noqa: E712
        user = (await session.execute(stmt)).scalar_one_or_none()
        if not user:
            return None

        raw_token = generate_secure_random_token(32)
        reset_token = PasswordResetToken(
            user_id=user.id,
            token_hash=hash_token(raw_token),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=settings.RESET_TOKEN_EXPIRE_MINUTES),
        )
        session.add(reset_token)
        await session.commit()
        return raw_token

    @classmethod
    async def reset_password(cls, session: AsyncSession, raw_token: str, new_password: str) -> None:
        """Validates reset token and sets new password."""
        token_hash = hash_token(raw_token)
        now = datetime.now(timezone.utc)

        stmt = select(PasswordResetToken).where(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > now,
        )
        token_record = (await session.execute(stmt)).scalar_one_or_none()
        if not token_record:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password reset token is invalid, expired, or has already been used.",
            )

        user = await session.get(User, token_record.user_id)
        if not user or user.is_deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User account not found.")

        # Update password
        user.hashed_password = hash_password(new_password)
        token_record.used_at = now

        # Revoke all active sessions for security
        await session.execute(
            update(RefreshSession)
            .where(
                RefreshSession.user_id == user.id,
                RefreshSession.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )

        await session.commit()

    @classmethod
    async def change_password(
        cls,
        session: AsyncSession,
        user: User,
        current_password: str,
        new_password: str,
    ) -> None:
        """Validates current password and updates to new password."""
        if not verify_password(current_password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password does not match.",
            )

        user.hashed_password = hash_password(new_password)

        # Revoke other sessions on password change
        await session.execute(
            update(RefreshSession)
            .where(
                RefreshSession.user_id == user.id,
                RefreshSession.revoked_at.is_(None),
            )
            .values(revoked_at=datetime.now(timezone.utc))
        )

        await session.commit()
