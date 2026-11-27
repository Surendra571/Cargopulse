import re
import uuid
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.models.enums import OrganizationType


class RegisterRequest(BaseModel):
    """Payload for registering a new customer organization and its first administrator."""
    full_name: str = Field(..., min_length=2, max_length=150, description="Full name of administrator")
    email: EmailStr = Field(..., description="Work email address")
    password: str = Field(..., min_length=8, max_length=128, description="Account password (min 8 characters)")
    confirm_password: str = Field(..., min_length=8, max_length=128)
    organization_name: str = Field(..., min_length=2, max_length=200, description="Legal company name")
    org_type: OrganizationType = Field(default=OrganizationType.MANUFACTURER, description="Organization business type")
    accept_terms: bool = Field(..., description="Consent to platform terms of service")

    @field_validator("password")
    @classmethod
    def validate_password_complexity(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long.")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter.")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter.")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit.")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", v):
            raise ValueError("Password must contain at least one special character.")
        return v

    @model_validator(mode="after")
    def verify_passwords_match(self) -> "RegisterRequest":
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        if not self.accept_terms:
            raise ValueError("You must accept the terms and conditions to proceed")
        return self


class LoginRequest(BaseModel):
    """Payload for email and password authentication."""
    email: EmailStr = Field(..., description="Registered user email")
    password: str = Field(..., min_length=1, max_length=128, description="User password")


class UserProfileResponse(BaseModel):
    """Public user identity and tenant affiliation details."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    phone: Optional[str] = None
    is_active: bool
    is_superadmin: bool
    organization_id: uuid.UUID
    organization_name: str
    organization_slug: str
    organization_type: OrganizationType
    roles: List[str] = []
    permissions: List[str] = []


class TokenResponse(BaseModel):
    """Successful authentication response with short-lived access token and identity summary."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserProfileResponse


class ForgotPasswordRequest(BaseModel):
    """Request payload to initiate password reset."""
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Request payload to complete password reset using a cryptographic token."""
    token: str = Field(..., min_length=10, description="Cryptographic reset token")
    new_password: str = Field(..., min_length=8, max_length=128, description="New password")
    confirm_password: str = Field(..., min_length=8, max_length=128)

    @model_validator(mode="after")
    def verify_passwords_match(self) -> "ResetPasswordRequest":
        if self.new_password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class ChangePasswordRequest(BaseModel):
    """Request payload for an authenticated user to change their password."""
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)
    confirm_password: str = Field(..., min_length=8, max_length=128)

    @model_validator(mode="after")
    def verify_passwords_match(self) -> "ChangePasswordRequest":
        if self.new_password != self.confirm_password:
            raise ValueError("Passwords do not match")
        if self.current_password == self.new_password:
            raise ValueError("New password must be different from the current password")
        return self


class MessageResponse(BaseModel):
    """Generic status and message response."""
    message: str
    success: bool = True
