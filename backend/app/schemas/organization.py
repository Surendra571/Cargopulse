import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import OrganizationType, UserRoleType


class OrganizationResponse(BaseModel):
    """Details of the tenant organization."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    org_type: OrganizationType
    is_active: bool
    billing_email: Optional[str] = None
    tax_identifier: Optional[str] = None
    settings: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: Optional[datetime] = None


class OrganizationUpdateRequest(BaseModel):
    """Payload to update organization profile details."""
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    billing_email: Optional[EmailStr] = None
    tax_identifier: Optional[str] = Field(None, max_length=50)


class OrganizationSettingsUpdateRequest(BaseModel):
    """Payload to update organization JSON settings."""
    settings: Dict[str, Any]


class PermissionResponse(BaseModel):
    """System permission representation."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    module: str
    description: Optional[str] = None


class RoleResponse(BaseModel):
    """Tenant or system role with mapped permissions."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    role_type: UserRoleType
    description: Optional[str] = None
    is_system_role: bool
    permissions: List[PermissionResponse] = Field(default_factory=list)


class TenantUserResponse(BaseModel):
    """User account within an organization scope."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    phone: Optional[str] = None
    is_active: bool
    is_superadmin: bool
    roles: List[str] = Field(default_factory=list)
    role_ids: List[uuid.UUID] = Field(default_factory=list)
    created_at: datetime
    last_login_at: Optional[datetime] = None


class InviteUserRequest(BaseModel):
    """Payload to invite or register a new user in the organization."""
    email: EmailStr
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    phone: Optional[str] = Field(None, max_length=30)
    role_ids: List[uuid.UUID] = Field(..., min_length=1)
    initial_password: Optional[str] = Field(None, min_length=8, max_length=128)


class UpdateUserRolesRequest(BaseModel):
    """Payload to update roles assigned to a user."""
    role_ids: List[uuid.UUID] = Field(..., min_length=1)


class UpdateUserStatusRequest(BaseModel):
    """Payload to activate or deactivate a user account."""
    is_active: bool


class LinkTransporterRequest(BaseModel):
    """Payload to associate a shared transporter with this organization."""
    transporter_id: uuid.UUID
    contract_reference: Optional[str] = Field(None, max_length=100)
    custom_rates: Optional[Dict[str, Any]] = None


class OrganizationTransporterResponse(BaseModel):
    """Transporter relationship with the tenant organization."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    transporter_id: uuid.UUID
    transporter_name: str
    transporter_code: str
    status: str
    contract_reference: Optional[str] = None
    custom_rates: Optional[Dict[str, Any]] = None
    created_at: datetime
