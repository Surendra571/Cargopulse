import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ExceptionPriority, ExceptionSeverity, ExceptionStatus, ExceptionType


class ExceptionUserSummary(BaseModel):
    id: str
    full_name: str
    email: str

    model_config = ConfigDict(from_attributes=True)


class ExceptionShipmentSummary(BaseModel):
    id: str
    tracking_number: str
    status: str
    origin_city: str
    destination_city: str

    model_config = ConfigDict(from_attributes=True)


class ExceptionTransporterSummary(BaseModel):
    id: str
    name: str
    code: str

    model_config = ConfigDict(from_attributes=True)


class ExceptionCreateRequest(BaseModel):
    shipment_id: Optional[uuid.UUID] = None
    transporter_id: Optional[uuid.UUID] = None
    exception_type: ExceptionType
    severity: ExceptionSeverity = ExceptionSeverity.MEDIUM
    priority: ExceptionPriority = ExceptionPriority.MEDIUM
    title: str = Field(..., min_length=3, max_length=200)
    description: str = Field(..., min_length=5, max_length=2000)
    assigned_owner_id: Optional[uuid.UUID] = None
    context_data: Optional[Dict[str, Any]] = None


class ExceptionUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    severity: Optional[ExceptionSeverity] = None
    priority: Optional[ExceptionPriority] = None
    assigned_owner_id: Optional[uuid.UUID] = None


class ExceptionAcknowledgeRequest(BaseModel):
    notes: Optional[str] = Field(None, max_length=500)


class ExceptionAssignRequest(BaseModel):
    assigned_owner_id: uuid.UUID
    notes: Optional[str] = Field(None, max_length=500)


class ExceptionEscalateRequest(BaseModel):
    target_severity: Optional[ExceptionSeverity] = ExceptionSeverity.CRITICAL
    escalation_reason: str = Field(..., min_length=3, max_length=500)


class ExceptionResolveRequest(BaseModel):
    root_cause: str = Field(..., min_length=3, max_length=1000)
    resolution_notes: str = Field(..., min_length=3, max_length=2000)


class ExceptionCloseRequest(BaseModel):
    closure_reason: str = Field(..., min_length=3, max_length=1000)


class ExceptionResponse(BaseModel):
    id: str
    organization_id: str
    shipment_id: Optional[str] = None
    transporter_id: Optional[str] = None
    exception_type: ExceptionType
    severity: ExceptionSeverity
    priority: str
    status: ExceptionStatus
    title: str
    description: str
    root_cause: Optional[str] = None
    escalation_level: int = 0
    escalated_at: Optional[datetime] = None
    reported_at: datetime
    acknowledged_at: Optional[datetime] = None
    acknowledged_by_user_id: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None
    closed_at: Optional[datetime] = None
    closed_by_user_id: Optional[str] = None
    closure_reason: Optional[str] = None
    reported_by_user_id: Optional[str] = None
    assigned_owner_id: Optional[str] = None
    context_data: Dict[str, Any] = {}
    created_at: datetime
    updated_at: datetime

    shipment: Optional[ExceptionShipmentSummary] = None
    transporter: Optional[ExceptionTransporterSummary] = None
    assigned_owner: Optional[ExceptionUserSummary] = None

    model_config = ConfigDict(from_attributes=True)


class ExceptionDetailResponse(ExceptionResponse):
    recovery_cases: List[Dict[str, Any]] = []
    audit_trail: List[Dict[str, Any]] = []


class ExceptionListResponse(BaseModel):
    items: List[ExceptionResponse]
    total: int
    page: int
    page_size: int
    pages: int


class ExceptionMetricsResponse(BaseModel):
    total_exceptions: int
    open_exceptions: int
    investigating_exceptions: int
    resolved_exceptions: int
    closed_exceptions: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    by_type: Dict[str, int]
    mean_resolution_hours: float
