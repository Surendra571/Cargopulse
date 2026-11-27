import uuid
from typing import AsyncGenerator, List, Optional

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.security import decode_access_token, verify_csrf_token
from app.models import User
from app.services.auth_service import AuthService

security_bearer = HTTPBearer(auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency yielding an async SQLAlchemy session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    session: AsyncSession = Depends(get_db),
) -> User:
    """
    Validates the JWT access token and resolves the user from PostgreSQL.
    Enforces that the user and organization are active.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token is invalid or has expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token subject invalid.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token user identity.",
        )

    user = await AuthService.get_user_with_relations(session, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account no longer exists.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been deactivated.",
        )

    if user.organization and not user.organization.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your organization is inactive.",
        )

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Convenience dependency verifying active user status."""
    return current_user


def validate_csrf(
    request: Request,
    x_csrf_token: Optional[str] = Header(None, alias="X-CSRF-Token"),
) -> None:
    """
    Validates CSRF token for mutating requests when cookie authentication is active.
    Safe methods (GET, HEAD, OPTIONS) do not require CSRF validation.
    """
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return

    csrf_cookie = request.cookies.get(settings.COOKIE_CSRF_NAME)
    refresh_cookie = request.cookies.get(settings.COOKIE_REFRESH_NAME)
    if refresh_cookie:
        if not x_csrf_token or not csrf_cookie or not verify_csrf_token(x_csrf_token, csrf_cookie):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF token validation failed. Request rejected.",
            )


def require_permission(permission_code: str):
    """
    Dependency factory that checks if the authenticated user has a specific permission.
    Superadmins and users with '*:*' or 'admin:all' automatically satisfy all permissions.
    Module-level wildcards (e.g. 'organization:*') are also honored.
    """
    async def _permission_checker(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if current_user.is_superadmin:
            return current_user

        _, permissions = AuthService.extract_roles_and_permissions(current_user)
        if "*:*" in permissions or "admin:all" in permissions or permission_code in permissions:
            return current_user

        module = permission_code.split(":")[0] if ":" in permission_code else None
        if module and f"{module}:*" in permissions:
            return current_user

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied: operation requires '{permission_code}'.",
        )

    return _permission_checker


def require_any_permission(permission_codes: List[str]):
    """
    Dependency factory that checks if the authenticated user has ANY of the specified permissions.
    """
    async def _any_permission_checker(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if current_user.is_superadmin:
            return current_user

        _, permissions = AuthService.extract_roles_and_permissions(current_user)
        if "*:*" in permissions or "admin:all" in permissions:
            return current_user

        for code in permission_codes:
            module = code.split(":")[0] if ":" in code else None
            if code in permissions or (module and f"{module}:*" in permissions):
                return current_user

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied: operation requires one of {permission_codes}.",
        )

    return _any_permission_checker


def require_role(roles_required: List[str]):
    """
    Dependency factory that checks if the authenticated user possesses ANY of the listed roles.
    Matches either role name or role_type enum value.
    """
    async def _role_checker(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if current_user.is_superadmin:
            return current_user

        roles, _ = AuthService.extract_roles_and_permissions(current_user)
        user_role_names = {r.upper() for r in roles}
        for ur in current_user.user_roles:
            if ur.role and ur.role.role_type:
                user_role_names.add(ur.role.role_type.value.upper())
                user_role_names.add(ur.role.role_type.name.upper())

        for req in roles_required:
            if req.upper() in user_role_names:
                return current_user

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: operation requires one of {roles_required} roles.",
        )

    return _role_checker


async def require_superadmin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Restricts access to global super-administrators only."""
    if not current_user.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Super Administrator privileges required.",
        )
    return current_user
