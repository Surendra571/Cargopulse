import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CommitmentStatus, RecoveryStatus, RecoveryStrategy


class CommitmentVehicleSummary(BaseModel):
    id: str
    license_plate: str
    vehicle_type: str
    capacity_kg: float

    model_config = ConfigDict(from_attributes=True)


class CommitmentDriverSummary(BaseModel):
    id: str
    first_name: str
    last_name: str
    phone: str
    license_number: str

    model_config = ConfigDict(from_attributes=True)


class CommitmentTransporterSummary(BaseModel):
    id: str
    name: str
    code: str
    phone: str
    reliability_score: float

    model_config = ConfigDict(from_attributes=True)


class CommitmentShipmentSummary(BaseModel):
    id: str
    tracking_number: str
    status: str
    origin_city: str
    origin_state: str
    destination_city: str
    destination_state: str
    total_weight_kg: float
    required_vehicle_type: str
    scheduled_pickup_time: datetime

    model_config = ConfigDict(from_attributes=True)


class PickupCommitmentResponse(BaseModel):
    id: str
    organization_id: str
    shipment_id: str
    transporter_id: str
    booking_id: Optional[str] = None
    committed_pickup_slot_start: datetime
    committed_pickup_slot_end: datetime
    pickup_deadline: datetime
    expected_arrival: Optional[datetime] = None
    status: CommitmentStatus
    actual_arrival_at: Optional[datetime] = None
    is_breached: bool = False
    breach_reason: Optional[str] = None
    penalties_incurred: float = 0.0
    created_at: datetime
    updated_at: datetime

    shipment: Optional[CommitmentShipmentSummary] = None
    transporter: Optional[CommitmentTransporterSummary] = None
    vehicle: Optional[CommitmentVehicleSummary] = None
    driver: Optional[CommitmentDriverSummary] = None

    model_config = ConfigDict(from_attributes=True)


class PickupCommitmentListResponse(BaseModel):
    items: List[PickupCommitmentResponse]
    total: int
    page: int
    page_size: int
    pages: int


class ArrivalReportRequest(BaseModel):
    actual_arrival_at: Optional[datetime] = None
    dock_number: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = Field(None, max_length=500)
    telematics_latitude: Optional[float] = None
    telematics_longitude: Optional[float] = None


class PickupStartRequest(BaseModel):
    started_at: Optional[datetime] = None
    bay_number: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = Field(None, max_length=500)


class PickupCompleteRequest(BaseModel):
    completed_at: Optional[datetime] = None
    bill_of_lading_number: Optional[str] = Field(None, max_length=100)
    loaded_weight_kg: Optional[float] = None
    seal_number: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = Field(None, max_length=500)


class PickupFailRequest(BaseModel):
    failure_reason: str = Field(..., min_length=3, max_length=500)
    penalty_amount: Optional[float] = Field(0.0, ge=0)
    notes: Optional[str] = Field(None, max_length=500)


class RecoveryCaseResponse(BaseModel):
    id: str
    organization_id: str
    exception_id: str
    shipment_id: Optional[str] = None
    case_number: str
    strategy: RecoveryStrategy
    status: RecoveryStatus
    approval_status: str
    proposed_solution: str
    estimated_cost_impact: float = 0.0
    original_transporter_id: Optional[str] = None
    replacement_transporter_id: Optional[str] = None
    replacement_booking_id: Optional[str] = None
    approved_by_user_id: Optional[str] = None
    approved_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    resolution_summary: Optional[str] = None
    ai_generated: bool = False
    failure_data: Optional[Dict[str, Any]] = None
    alternatives_data: Optional[List[Dict[str, Any]]] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RecoveryCaseListResponse(BaseModel):
    items: List[RecoveryCaseResponse]
    total: int
    page: int
    page_size: int
    pages: int


class RecoveryCaseDetailResponse(RecoveryCaseResponse):
    pass


class RecoveryApproveRequest(BaseModel):
    replacement_transporter_id: uuid.UUID
    agreed_rate: Optional[float] = Field(None, ge=0)
    vehicle_id: Optional[uuid.UUID] = None
    driver_id: Optional[uuid.UUID] = None
    notes: Optional[str] = Field(None, max_length=500)


class PickupScanResponse(BaseModel):
    scanned_count: int
    reminders_sent: int
    at_risk_flagged: int
    missed_detected: int
    exceptions_created: int
    recovery_cases_opened: int
    simulated_now: str


class SimulateScenarioRequest(BaseModel):
    customer_name: Optional[str] = "Acme Retail Logistics"
    scheduled_hour_offset: int = Field(default=0, description="Hours relative to reference 10:00 AM scenario")


class SimulateScenarioResponse(BaseModel):
    scenario_id: str
    status: str
    shipment_id: str
    tracking_number: str
    transporter_a_name: str
    transporter_c_name: str
    pickup_deadline: str
    milestones: List[Dict[str, Any]]
    recovery_case_number: str
    replacement_booking_ref: str
    assignment_history: List[Dict[str, Any]]
