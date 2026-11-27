import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


# ==========================================
# Enums / Constants
# ==========================================

class TransporterVerificationStatus:
    REGISTERED = "REGISTERED"
    DOCUMENTS_SUBMITTED = "DOCUMENTS_SUBMITTED"
    UNDER_VERIFICATION = "UNDER_VERIFICATION"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    SUSPENDED = "SUSPENDED"

    ALL = [
        REGISTERED,
        DOCUMENTS_SUBMITTED,
        UNDER_VERIFICATION,
        VERIFIED,
        REJECTED,
        SUSPENDED,
    ]


class TransporterAccountStatus:
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    SUSPENDED = "SUSPENDED"


class VehicleStatusEnum:
    ACTIVE = "ACTIVE"
    MAINTENANCE = "MAINTENANCE"
    EXPIRED_DOCUMENTS = "EXPIRED_DOCUMENTS"
    INACTIVE = "INACTIVE"


class DriverStatusEnum:
    ACTIVE = "ACTIVE"
    ON_DUTY = "ON_DUTY"
    OFF_DUTY = "OFF_DUTY"
    EXPIRED_LICENSE = "EXPIRED_LICENSE"
    SUSPENDED = "SUSPENDED"


# ==========================================
# Service Area Schemas
# ==========================================

class ServiceAreaCreateRequest(BaseModel):
    origin_region: str = Field(..., min_length=2, max_length=100, description="Origin state, city, or hub")
    destination_region: str = Field(..., min_length=2, max_length=100, description="Destination state, city, or hub")
    origin_postal_code_prefix: Optional[str] = Field(None, max_length=10)
    destination_postal_code_prefix: Optional[str] = Field(None, max_length=10)
    estimated_transit_hours: int = Field(default=24, ge=1, le=720)


class ServiceAreaResponse(BaseModel):
    id: str
    transporter_id: str
    origin_region: str
    destination_region: str
    origin_postal_code_prefix: Optional[str] = None
    destination_postal_code_prefix: Optional[str] = None
    estimated_transit_hours: int
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# Vehicle Schemas
# ==========================================

class VehicleCreateRequest(BaseModel):
    transporter_id: uuid.UUID
    license_plate: str = Field(..., min_length=3, max_length=50, description="Vehicle registration plate / number")
    vehicle_type: str = Field(..., min_length=2, max_length=50, description="e.g. 53' Dry Van, Flatbed 48', Reefer")
    capacity_kg: float = Field(..., gt=0, description="Maximum cargo weight capacity in kg")
    volume_cbm: Optional[float] = Field(None, ge=0, description="Volume capacity in cubic meters")
    rc_number: Optional[str] = Field(None, max_length=50, description="Registration Certificate number")
    insurance_expiry: Optional[datetime] = Field(None, description="Insurance policy expiration date")
    fitness_expiry: Optional[datetime] = Field(None, description="Vehicle fitness / inspection certificate expiry")
    telematics_device_id: Optional[str] = Field(None, max_length=100, description="GPS / IoT device identifier")
    is_available: bool = Field(default=True)


class VehicleUpdateRequest(BaseModel):
    vehicle_type: Optional[str] = Field(None, min_length=2, max_length=50)
    capacity_kg: Optional[float] = Field(None, gt=0)
    volume_cbm: Optional[float] = Field(None, ge=0)
    rc_number: Optional[str] = Field(None, max_length=50)
    insurance_expiry: Optional[datetime] = None
    fitness_expiry: Optional[datetime] = None
    telematics_device_id: Optional[str] = Field(None, max_length=100)
    is_available: Optional[bool] = None


class VehicleListItem(BaseModel):
    id: str
    transporter_id: str
    transporter_name: str
    license_plate: str
    vehicle_type: str
    capacity_kg: float
    volume_cbm: Optional[float] = None
    is_available: bool
    status: str
    has_expired_documents: bool
    insurance_expiry: Optional[datetime] = None
    fitness_expiry: Optional[datetime] = None
    rc_number: Optional[str] = None
    telematics_device_id: Optional[str] = None
    assigned_driver_id: Optional[str] = None
    assigned_driver_name: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedVehiclesResponse(BaseModel):
    items: List[VehicleListItem]
    total: int
    page: int
    page_size: int
    total_pages: int


# ==========================================
# Driver Schemas
# ==========================================

class DriverCreateRequest(BaseModel):
    transporter_id: uuid.UUID
    first_name: str = Field(..., min_length=2, max_length=100)
    last_name: str = Field(..., min_length=2, max_length=100)
    phone: str = Field(..., min_length=7, max_length=30)
    license_number: str = Field(..., min_length=4, max_length=50)
    license_expiry: Optional[datetime] = None
    is_available: bool = Field(default=True)
    assigned_vehicle_id: Optional[uuid.UUID] = None


class DriverUpdateRequest(BaseModel):
    first_name: Optional[str] = Field(None, min_length=2, max_length=100)
    last_name: Optional[str] = Field(None, min_length=2, max_length=100)
    phone: Optional[str] = Field(None, min_length=7, max_length=30)
    license_number: Optional[str] = Field(None, min_length=4, max_length=50)
    license_expiry: Optional[datetime] = None
    is_available: Optional[bool] = None
    assigned_vehicle_id: Optional[uuid.UUID] = None


class DriverAssignmentRequest(BaseModel):
    vehicle_id: Optional[uuid.UUID] = Field(None, description="Vehicle ID to assign driver to, or null to unassign")


class DriverListItem(BaseModel):
    id: str
    transporter_id: str
    transporter_name: str
    first_name: str
    last_name: str
    full_name: str
    phone: str
    license_number: str
    license_number_masked: str
    license_expiry: Optional[datetime] = None
    is_license_expired: bool
    is_available: bool
    status: str
    assigned_vehicle_id: Optional[str] = None
    assigned_vehicle_plate: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedDriversResponse(BaseModel):
    items: List[DriverListItem]
    total: int
    page: int
    page_size: int
    total_pages: int


# ==========================================
# Transporter Schemas
# ==========================================

class TransporterDocumentItem(BaseModel):
    doc_type: str = Field(..., description="e.g. MOTOR_CARRIER_PERMIT, INSURANCE_CERTIFICATE, GSTIN_CERTIFICATE, PAN_CARD")
    document_number: Optional[str] = None
    file_url: str
    expiry_date: Optional[datetime] = None
    submitted_at: datetime
    status: str = "PENDING_VERIFICATION"  # PENDING_VERIFICATION, VERIFIED, REJECTED


class TransporterDocumentUploadRequest(BaseModel):
    doc_type: str = Field(..., min_length=2, max_length=100)
    document_number: Optional[str] = Field(None, max_length=100)
    file_url: str = Field(..., min_length=5, max_length=500)
    expiry_date: Optional[datetime] = None


class TransporterCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=255, description="Transporter business or legal name")
    code: Optional[str] = Field(None, max_length=50, description="Carrier identifier code e.g. TRP-APEX")
    contact_person: Optional[str] = Field(None, max_length=150)
    phone: str = Field(..., min_length=7, max_length=30)
    email: Optional[str] = Field(None, max_length=255)
    gstin: Optional[str] = Field(None, max_length=30, description="Tax / GST identification number")
    service_regions: List[str] = Field(default_factory=list, description="List of operating regions or states")
    operating_routes: List[str] = Field(default_factory=list, description="Primary corridors e.g. 'Detroit -> Chicago'")
    vehicle_categories: List[str] = Field(default_factory=list, description="Fleet vehicle categories supported")
    max_cargo_capacity_kg: Optional[float] = Field(None, ge=0)


class TransporterUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    contact_person: Optional[str] = Field(None, max_length=150)
    phone: Optional[str] = Field(None, min_length=7, max_length=30)
    email: Optional[str] = Field(None, max_length=255)
    gstin: Optional[str] = Field(None, max_length=30)
    service_regions: Optional[List[str]] = None
    operating_routes: Optional[List[str]] = None
    vehicle_categories: Optional[List[str]] = None
    max_cargo_capacity_kg: Optional[float] = Field(None, ge=0)
    is_active: Optional[bool] = None


class TransporterVerificationRequest(BaseModel):
    status: str = Field(..., description="REGISTERED, DOCUMENTS_SUBMITTED, UNDER_VERIFICATION, VERIFIED, REJECTED, SUSPENDED")
    verification_notes: Optional[str] = Field(None, max_length=1000)

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        upper_v = v.upper()
        if upper_v not in TransporterVerificationStatus.ALL:
            raise ValueError(f"Invalid verification status. Must be one of: {', '.join(TransporterVerificationStatus.ALL)}")
        return upper_v


class TransporterListItem(BaseModel):
    id: str
    organization_id: str
    name: str
    code: str
    contact_person: Optional[str] = None
    phone: str
    email: Optional[str] = None
    gstin: Optional[str] = None
    is_active: bool
    account_status: str
    verification_status: str
    reliability_score: float
    total_deliveries: int
    on_time_deliveries: int
    on_time_delivery_rate: float
    total_vehicles: int
    active_vehicles: int
    total_drivers: int
    active_drivers: int
    service_regions: List[str] = []
    vehicle_categories: List[str] = []
    max_cargo_capacity_kg: Optional[float] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TransporterPerformanceSummary(BaseModel):
    reliability_score: float
    total_deliveries: int
    on_time_deliveries: int
    on_time_rate: float
    active_exceptions: int
    accepted_bookings_count: int
    rejected_bookings_count: int
    total_fleet_capacity_kg: float


class TransporterBookingSummaryItem(BaseModel):
    id: str
    shipment_id: str
    shipment_tracking_number: str
    origin_summary: str
    destination_summary: str
    status: str
    offered_rate: Optional[float] = None
    agreed_rate: Optional[float] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TransporterDetailResponse(BaseModel):
    id: str
    organization_id: str
    name: str
    code: str
    contact_person: Optional[str] = None
    phone: str
    email: Optional[str] = None
    gstin: Optional[str] = None
    is_active: bool
    account_status: str
    verification_status: str
    verification_notes: Optional[str] = None
    verified_at: Optional[datetime] = None
    verified_by_user: Optional[str] = None
    service_regions: List[str] = []
    operating_routes: List[str] = []
    vehicle_categories: List[str] = []
    max_cargo_capacity_kg: Optional[float] = None
    documents: List[TransporterDocumentItem] = []

    # Fleet & Operations
    vehicles: List[VehicleListItem] = []
    drivers: List[DriverListItem] = []
    service_areas: List[ServiceAreaResponse] = []
    recent_bookings: List[TransporterBookingSummaryItem] = []
    performance: TransporterPerformanceSummary

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedTransportersResponse(BaseModel):
    items: List[TransporterListItem]
    total: int
    page: int
    page_size: int
    total_pages: int
