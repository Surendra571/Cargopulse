import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import BookingStatus


# ============================================================================
# Nested Summary DTOs
# ============================================================================

class BookingVehicleSummary(BaseModel):
    id: str
    license_plate: str
    vehicle_type: str
    capacity_kg: float
    volume_cbm: Optional[float] = None
    is_available: bool = True
    insurance_expiry: Optional[datetime] = None
    fitness_expiry: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class BookingDriverSummary(BaseModel):
    id: str
    first_name: str
    last_name: str
    phone: str
    license_number: str
    license_expiry: Optional[datetime] = None
    account_status: str = "ACTIVE"

    model_config = ConfigDict(from_attributes=True)


class BookingTransporterSummary(BaseModel):
    id: str
    name: str
    code: str
    phone: str
    email: Optional[str] = None
    verification_status: str
    reliability_score: float

    model_config = ConfigDict(from_attributes=True)


class BookingShipmentSummary(BaseModel):
    id: str
    tracking_number: str
    status: str
    customer_name: Optional[str] = None
    origin_name: str
    origin_city: str
    origin_state: str
    destination_name: str
    destination_city: str
    destination_state: str
    total_weight_kg: float
    required_vehicle_type: str
    scheduled_pickup_time: datetime
    expected_delivery_time: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Request Schemas
# ============================================================================

class BookingCreateRequest(BaseModel):
    shipment_id: uuid.UUID
    transporter_id: uuid.UUID
    offered_rate: Optional[float] = Field(None, ge=0, description="Offered freight payment tariff")
    agreed_rate: Optional[float] = Field(None, ge=0, description="Pre-negotiated agreed rate")
    expires_in_hours: int = Field(default=24, ge=1, le=168, description="Booking tender lifespan in hours")
    vehicle_id: Optional[uuid.UUID] = Field(None, description="Pre-assigned vehicle if known")
    driver_id: Optional[uuid.UUID] = Field(None, description="Pre-assigned driver if known")
    booking_notes: Optional[str] = Field(None, max_length=500, description="Dispatch instructions or pickup terms")


class BookingAcceptRequest(BaseModel):
    agreed_rate: Optional[float] = Field(None, ge=0, description="Carrier confirmed agreed rate")
    response_notes: Optional[str] = Field(None, max_length=500, description="Transporter acceptance notes")
    vehicle_id: Optional[uuid.UUID] = Field(None, description="Designated vehicle unit")
    driver_id: Optional[uuid.UUID] = Field(None, description="Designated driver operator")


class BookingRejectRequest(BaseModel):
    rejection_reason: str = Field(..., min_length=3, max_length=500, description="Operational justification for tender rejection")
    response_notes: Optional[str] = Field(None, max_length=500)


class BookingAssignResourceRequest(BaseModel):
    vehicle_id: uuid.UUID = Field(..., description="Eligible vehicle ID with capacity and valid docs")
    driver_id: uuid.UUID = Field(..., description="Eligible driver ID with unexpired license")
    notes: Optional[str] = Field(None, max_length=500, description="Dispatch handover notes")


class BookingCancelRequest(BaseModel):
    cancellation_reason: str = Field(..., min_length=3, max_length=500, description="Reason for cancelling tender")


# ============================================================================
# Response Schemas
# ============================================================================

class BookingResponse(BaseModel):
    id: str
    organization_id: str
    booking_reference: str
    status: BookingStatus
    shipment_id: str
    transporter_id: str
    offered_rate: Optional[float] = None
    agreed_rate: Optional[float] = None
    expires_at: datetime
    response_notes: Optional[str] = None
    rejection_reason: Optional[str] = None
    responded_at: Optional[datetime] = None
    confirmed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    shipment: Optional[BookingShipmentSummary] = None
    transporter: Optional[BookingTransporterSummary] = None
    vehicle: Optional[BookingVehicleSummary] = None
    driver: Optional[BookingDriverSummary] = None
    assignment_id: Optional[str] = None
    is_expired: bool = False

    model_config = ConfigDict(from_attributes=True)


class BookingListResponse(BaseModel):
    items: List[BookingResponse]
    total: int
    page: int
    page_size: int
    pages: int


class BookingDetailResponse(BookingResponse):
    events: List[Dict[str, Any]] = []
    audit_logs: List[Dict[str, Any]] = []
