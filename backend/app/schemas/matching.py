import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ScorecardComponent(BaseModel):
    score: float = Field(..., description="Raw component score (0-100)")
    weight: float = Field(..., description="Component weight (0-1.0)")
    weighted_score: float = Field(..., description="Score * Weight")
    explanation: str = Field(..., description="Transparent audit justification for this score")


class ScorecardBreakdown(BaseModel):
    pickup_reliability: ScorecardComponent
    ontime_delivery: ScorecardComponent
    booking_acceptance: ScorecardComponent
    route_suitability: ScorecardComponent
    cost_competitiveness: ScorecardComponent


class MatchedVehicleItem(BaseModel):
    id: str
    license_plate: str
    vehicle_type: str
    capacity_kg: float
    volume_cbm: Optional[float] = None
    is_available: bool
    insurance_expiry: Optional[datetime] = None
    fitness_expiry: Optional[datetime] = None


class TransporterRecommendationItem(BaseModel):
    transporter_id: str
    transporter_name: str
    transporter_code: str
    phone: str
    email: Optional[str] = None
    gstin: Optional[str] = None
    verification_status: str
    account_status: str
    reliability_score: float

    # Matching & Ranking metrics
    match_score: float = Field(..., description="Overall normalized match score (0-100)")
    rank: int = Field(..., description="Recommendation ranking (1 = best fit)")
    is_eligible: bool = True
    ineligibility_reasons: List[str] = []

    # Explanations & scorecard
    scorecard: ScorecardBreakdown
    recommendation_summary: str = Field(..., description="Human-readable summary of carrier fit")
    is_new_transporter: bool = False

    # Capacity & fleet fit
    eligible_vehicles: List[MatchedVehicleItem] = []
    total_eligible_vehicles_count: int = 0
    route_suitability_type: str = Field(..., description="DIRECT_LANE, OPERATING_CORRIDOR, REGIONAL_COVERAGE, or GENERAL")
    estimated_cost: Optional[float] = None
    currency: str = "USD"


class MatchingAuditRecordResponse(BaseModel):
    action_id: str
    action_type: str
    confidence_score: float
    decision_summary: str
    prompt_summary: str
    requires_human_approval: bool
    created_at: datetime
    approved_at: Optional[datetime] = None
    approved_by_user_id: Optional[str] = None


class TransporterMatchingResponse(BaseModel):
    shipment_id: str
    tracking_number: str
    origin_city: str
    origin_state: str
    destination_city: str
    destination_state: str
    total_weight_kg: float
    required_vehicle_type: str
    scheduled_pickup_time: datetime
    expected_delivery_time: datetime

    total_carriers_evaluated: int
    eligible_carriers_count: int
    excluded_carriers_count: int

    recommendations: List[TransporterRecommendationItem]
    excluded: List[TransporterRecommendationItem] = []
    weights_used: Dict[str, float]
    audit_record: Optional[MatchingAuditRecordResponse] = None
    disclaimer: str = "Recommendations are algorithmic rankings based on historical compliance and fleet capacity. Past performance does not guarantee future operational execution."


class TransporterSelectionRequest(BaseModel):
    transporter_id: uuid.UUID
    vehicle_id: Optional[uuid.UUID] = None
    driver_id: Optional[uuid.UUID] = None
    agreed_rate: Optional[float] = Field(None, ge=0, description="Agreed freight rate / quotation")
    booking_notes: Optional[str] = Field(None, max_length=500, description="Special instructions or dispatch terms")


class TransporterSelectionResponse(BaseModel):
    success: bool
    message: str
    shipment_id: str
    tracking_number: str
    transporter_id: str
    transporter_name: str
    transporter_code: str
    booking_id: Optional[str] = None
    assignment_id: Optional[str] = None
    shipment_status: str
    agreed_rate: Optional[float] = None
    audit_log_id: str
    selected_at: datetime
