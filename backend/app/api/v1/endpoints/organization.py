import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_current_user,
    get_db,
    require_permission,
    validate_csrf,
)
from app.models import User
from app.schemas.auth import MessageResponse
from app.schemas.organization import (
    InviteUserRequest,
    LinkTransporterRequest,
    OrganizationResponse,
    OrganizationSettingsUpdateRequest,
    OrganizationTransporterResponse,
    OrganizationUpdateRequest,
    PermissionResponse,
    RoleResponse,
    TenantUserResponse,
    UpdateUserRolesRequest,
    UpdateUserStatusRequest,
)
from app.services.organization_service import OrganizationService

router = APIRouter(prefix="/organizations", tags=["Organizations & RBAC"])


# 1. Organization Profile
@router.get(
    "/me",
    response_model=OrganizationResponse,
    summary="Get current organization profile",
)
async def get_my_organization(
    current_user: User = Depends(require_permission("organization:read")),
    session: AsyncSession = Depends(get_db),
) -> OrganizationResponse:
    """Retrieves tenant organization details for the authenticated user's organization."""
    return await OrganizationService.get_organization(
        session, current_user.organization_id
    )


@router.put(
    "/me",
    response_model=OrganizationResponse,
    dependencies=[Depends(validate_csrf)],
    summary="Update organization profile",
)
async def update_my_organization(
    payload: OrganizationUpdateRequest,
    current_user: User = Depends(require_permission("organization:manage")),
    session: AsyncSession = Depends(get_db),
) -> OrganizationResponse:
    """Updates organization profile information with tenant boundary isolation."""
    return await OrganizationService.update_organization(
        session, current_user.organization_id, payload, current_user
    )


# 2. Organization Settings
@router.get(
    "/me/settings",
    response_model=Dict[str, Any],
    summary="Get organization configuration settings",
)
async def get_my_organization_settings(
    current_user: User = Depends(require_permission("organization:read")),
    session: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieves operational settings and configuration parameters for this organization."""
    return await OrganizationService.get_settings(
        session, current_user.organization_id
    )


@router.patch(
    "/me/settings",
    response_model=Dict[str, Any],
    dependencies=[Depends(validate_csrf)],
    summary="Update organization configuration settings",
)
async def update_my_organization_settings(
    payload: OrganizationSettingsUpdateRequest,
    current_user: User = Depends(require_permission("organization:manage")),
    session: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Updates custom settings and operational thresholds for this organization."""
    return await OrganizationService.update_settings(
        session, current_user.organization_id, payload.settings, current_user
    )


# 3. Roles and Permissions Directory
@router.get(
    "/me/roles",
    response_model=List[RoleResponse],
    summary="List roles available to this organization",
)
async def list_organization_roles(
    current_user: User = Depends(require_permission("roles:read")),
    session: AsyncSession = Depends(get_db),
) -> List[RoleResponse]:
    """Lists system and tenant-specific roles with assigned permissions."""
    return await OrganizationService.list_roles(
        session, current_user.organization_id, current_user
    )


@router.get(
    "/me/permissions",
    response_model=List[PermissionResponse],
    summary="List all platform permissions",
)
async def list_platform_permissions(
    current_user: User = Depends(require_permission("roles:read")),
    session: AsyncSession = Depends(get_db),
) -> List[PermissionResponse]:
    """Lists all registered platform permissions."""
    return await OrganizationService.list_permissions(session)


# 4. User Management
@router.get(
    "/me/users",
    response_model=List[TenantUserResponse],
    summary="List organization users",
)
async def list_organization_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    search: Optional[str] = Query(None, description="Search by name or email"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    current_user: User = Depends(require_permission("users:read")),
    session: AsyncSession = Depends(get_db),
) -> List[TenantUserResponse]:
    """Lists all user accounts belonging to the tenant organization."""
    return await OrganizationService.list_tenant_users(
        session,
        current_user.organization_id,
        skip=skip,
        limit=limit,
        search=search,
        is_active=is_active,
    )


@router.post(
    "/me/users",
    response_model=TenantUserResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(validate_csrf)],
    summary="Invite or add user to organization",
)
async def invite_organization_user(
    payload: InviteUserRequest,
    current_user: User = Depends(require_permission("users:manage")),
    session: AsyncSession = Depends(get_db),
) -> TenantUserResponse:
    """Provisions a new user account strictly within the current tenant organization."""
    return await OrganizationService.invite_or_create_user(
        session, current_user.organization_id, payload, current_user
    )


@router.get(
    "/me/users/{user_id}",
    response_model=TenantUserResponse,
    summary="Get user details by ID",
)
async def get_organization_user(
    user_id: uuid.UUID,
    current_user: User = Depends(require_permission("users:read")),
    session: AsyncSession = Depends(get_db),
) -> TenantUserResponse:
    """
    Retrieves user profile within tenant boundary.
    Enforces tenant isolation: access to users outside caller's organization returns 404.
    """
    return await OrganizationService.get_tenant_user(
        session, current_user.organization_id, user_id
    )


@router.put(
    "/me/users/{user_id}/roles",
    response_model=TenantUserResponse,
    dependencies=[Depends(validate_csrf)],
    summary="Update roles assigned to a user",
)
async def update_user_roles(
    user_id: uuid.UUID,
    payload: UpdateUserRolesRequest,
    current_user: User = Depends(require_permission("users:manage")),
    session: AsyncSession = Depends(get_db),
) -> TenantUserResponse:
    """Updates roles for a tenant user with strict privilege escalation prevention."""
    return await OrganizationService.update_user_roles(
        session, current_user.organization_id, user_id, payload.role_ids, current_user
    )


@router.patch(
    "/me/users/{user_id}/status",
    response_model=TenantUserResponse,
    dependencies=[Depends(validate_csrf)],
    summary="Activate or deactivate user account",
)
async def update_user_status(
    user_id: uuid.UUID,
    payload: UpdateUserStatusRequest,
    current_user: User = Depends(require_permission("users:manage")),
    session: AsyncSession = Depends(get_db),
) -> TenantUserResponse:
    """
    Activates or deactivates a user account.
    Deactivating terminates all active refresh sessions immediately.
    """
    return await OrganizationService.update_user_status(
        session, current_user.organization_id, user_id, payload.is_active, current_user
    )


@router.delete(
    "/me/users/{user_id}",
    response_model=MessageResponse,
    dependencies=[Depends(validate_csrf)],
    summary="Revoke user access",
)
async def revoke_user_access(
    user_id: uuid.UUID,
    current_user: User = Depends(require_permission("users:manage")),
    session: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """
    Permanently revokes user access (soft-delete + immediate session revocation).
    Prevents self-revocation and cross-tenant IDOR.
    """
    await OrganizationService.revoke_user_access(
        session, current_user.organization_id, user_id, current_user
    )
    return MessageResponse(message="User access has been permanently revoked.")


# 5. Multi-Tenant Transporter Partnerships
@router.get(
    "/me/transporters",
    response_model=List[OrganizationTransporterResponse],
    summary="List transporters linked to this organization",
)
async def list_linked_transporters(
    current_user: User = Depends(require_permission("transporters:read")),
    session: AsyncSession = Depends(get_db),
) -> List[OrganizationTransporterResponse]:
    """Lists all transporters linked with this manufacturer organization."""
    return await OrganizationService.list_linked_transporters(
        session, current_user.organization_id
    )


@router.post(
    "/me/transporters/link",
    response_model=OrganizationTransporterResponse,
    dependencies=[Depends(validate_csrf)],
    summary="Link a transporter to this organization",
)
async def link_transporter(
    payload: LinkTransporterRequest,
    current_user: User = Depends(require_permission("transporters:manage")),
    session: AsyncSession = Depends(get_db),
) -> OrganizationTransporterResponse:
    """Links a shared master carrier profile to this organization without duplicating fleet/drivers."""
    return await OrganizationService.link_transporter(
        session, current_user.organization_id, payload, current_user
    )


@router.delete(
    "/me/transporters/{transporter_id}",
    response_model=MessageResponse,
    dependencies=[Depends(validate_csrf)],
    summary="Unlink transporter from organization",
)
async def unlink_transporter(
    transporter_id: uuid.UUID,
    current_user: User = Depends(require_permission("transporters:manage")),
    session: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Terminates carrier association for this organization."""
    await OrganizationService.unlink_transporter(
        session, current_user.organization_id, transporter_id, current_user
    )
    return MessageResponse(message="Transporter association has been terminated.")
