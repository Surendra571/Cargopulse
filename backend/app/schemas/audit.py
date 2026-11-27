import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    user_id: Optional[uuid.UUID] = None
    actor_email: Optional[str] = None
    action: str
    resource_type: str = Field(..., description="Type of audited entity, e.g. Shipment, User, Booking")
    resource_id: uuid.UUID = Field(..., description="UUID of audited entity")
    correlation_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    changes: Dict[str, Any] = Field(default_factory=dict, description="Sanitized before/after state diff or metadata")
    created_at: datetime


class AuditLogListResponse(BaseModel):
    items: List[AuditLogResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class CreateAuditEventRequest(BaseModel):
    action: str = Field(..., description="Action name, e.g. PERMISSION_CHANGED, MANUAL_OVERRIDE")
    resource_type: str = Field(..., description="Target resource type")
    resource_id: uuid.UUID = Field(..., description="Target resource UUID")
    correlation_id: Optional[str] = Field(None, description="Client or distributed request correlation ID")
    before: Optional[Dict[str, Any]] = Field(None, description="Previous state snapshot")
    after: Optional[Dict[str, Any]] = Field(None, description="New state snapshot")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional contextual parameters (sanitized)")
