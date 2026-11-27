import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ReconciliationItemResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    shipment_id: uuid.UUID
    reconciliation_id: Optional[uuid.UUID]
    category: str
    status: str
    expected_value: Optional[str]
    actual_value: Optional[str]
    discrepancy_delta: Optional[str]
    severity: str
    is_matched: bool
    is_missing_data: bool
    assigned_user_id: Optional[uuid.UUID]
    investigation_notes: Optional[str]
    resolution_notes: Optional[str]
    resolved_by_user_id: Optional[uuid.UUID]
    resolved_at: Optional[datetime]
    closed_at: Optional[datetime]
    item_metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ReconciliationRecordSummary(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    shipment_id: uuid.UUID
    tracking_number: Optional[str] = None
    transporter_id: uuid.UUID
    transporter_name: Optional[str] = None
    status: str
    base_freight_charge: float
    final_payable_amount: float
    total_discrepancies: int
    resolved_discrepancies: int
    has_mismatches: bool
    has_missing_data: bool
    invoice_number: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ReconciliationDetailResponse(BaseModel):
    reconciliation: ReconciliationRecordSummary
    shipment_summary: Dict[str, Any]
    items: List[ReconciliationItemResponse]
    audit_history: List[Dict[str, Any]] = Field(default_factory=list)


class UpdateDiscrepancyItemRequest(BaseModel):
    assigned_user_id: Optional[uuid.UUID] = None
    investigation_notes: Optional[str] = None
    resolution_notes: Optional[str] = None
    status: Optional[str] = None  # OPEN, INVESTIGATING, RESOLVED, CLOSED


class CloseReconciliationRequest(BaseModel):
    closure_notes: Optional[str] = None
