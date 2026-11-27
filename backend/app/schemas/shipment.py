import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


# ==========================================
# Enums / Constants
# ==========================================

class CargoCategoryEnum:
    GENERAL_FREIGHT = "GENERAL_FREIGHT"
    AUTOMOTIVE = "AUTOMOTIVE"
    ELECTRONICS = "ELECTRONICS"
    PERISHABLES = "PERISHABLES"
    HAZARDOUS = "HAZARDOUS"
    HEAVY_MACHINERY = "HEAVY_MACHINERY"
    PHARMACEUTICALS = "PHARMACEUTICALS"
    RAW_MATERIALS = "RAW_MATERIALS"


class VehicleTypeEnum:
    DRY_VAN_53 = "53' Dry Van"
    FLATBED_48 = "Flatbed 48'"
    REFRIGERATED_53 = "Refrigerated 53'"
    BOX_TRUCK_26 = "Box Truck 26'"
    STEP_DECK = "Step Deck"
    CONTAINER_CHASSIS = "Container Chassis"


class ShipmentPriorityEnum:
    STANDARD = "STANDARD"
    EXPEDITED = "EXPEDITED"
    CRITICAL = "CRITICAL"


class PackageUnitEnum:
    PALLETS = "PALLETS"
    BOXES = "BOXES"
    CARTONS = "CARTONS"
    CRATES = "CRATES"
    DRUMS = "DRUMS"
    UNITS = "UNITS"


# ==========================================
# Request Schemas
# ==========================================

class ShipmentCreateRequest(BaseModel):
    # Customer Info
    customer_name: str = Field(..., min_length=2, max_length=150, description="Customer or consignor business name")
    customer_reference: Optional[str] = Field(None, max_length=100, description="Customer reference or PO number")

    # Origin
    origin_name: str = Field(..., min_length=2, max_length=200, description="Origin facility name")
    origin_address: str = Field(..., min_length=5, description="Origin street address")
    origin_city: str = Field(..., min_length=2, max_length=100)
    origin_state: str = Field(..., min_length=2, max_length=100)
    origin_postal_code: str = Field(..., min_length=3, max_length=20)
    origin_dock_number: Optional[str] = Field(None, max_length=50)
    origin_contact_name: str = Field(..., min_length=2, max_length=150)
    origin_contact_phone: str = Field(..., min_length=7, max_length=30)

    # Destination
    destination_name: str = Field(..., min_length=2, max_length=200, description="Destination facility name")
    destination_address: str = Field(..., min_length=5, description="Destination street address")
    destination_city: str = Field(..., min_length=2, max_length=100)
    destination_state: str = Field(..., min_length=2, max_length=100)
    destination_postal_code: str = Field(..., min_length=3, max_length=20)
    destination_dock_number: Optional[str] = Field(None, max_length=50)
    destination_contact_name: str = Field(..., min_length=2, max_length=150)
    destination_contact_phone: str = Field(..., min_length=7, max_length=30)

    # Cargo Details
    goods_description: str = Field(..., min_length=3, description="Detailed description of cargo")
    cargo_category: str = Field(default="GENERAL_FREIGHT", max_length=50)
    total_weight_kg: float = Field(..., gt=0, description="Cargo weight in kg (must be greater than 0)")
    package_count: int = Field(..., gt=0, description="Quantity / piece count (must be > 0)")
    package_unit: str = Field(default="PALLETS", max_length=30)
    total_volume_cbm: Optional[float] = Field(None, ge=0)
    required_vehicle_type: str = Field(default="53' Dry Van", max_length=50)
    is_hazardous: bool = Field(default=False)

    # Schedule & Timings
    scheduled_pickup_time: datetime = Field(..., description="Pickup deadline (UTC)")
    expected_delivery_time: datetime = Field(..., description="Expected delivery deadline (UTC)")

    # Priorities & Instructions
    priority: str = Field(default="STANDARD", max_length=20)
    special_instructions: Optional[str] = Field(None, description="Handling or dock instructions")
    invoice_number: Optional[str] = Field(None, max_length=100)
    invoice_value: Optional[float] = Field(None, ge=0)

    @field_validator("expected_delivery_time")
    @classmethod
    def validate_delivery_after_pickup(cls, v: datetime, info: Any) -> datetime:
        pickup = info.data.get("scheduled_pickup_time")
        if pickup and v <= pickup:
            raise ValueError("Expected delivery time must be strictly after the scheduled pickup deadline.")
        return v


class ShipmentUpdateRequest(BaseModel):
    # Customer Info
    customer_name: Optional[str] = Field(None, min_length=2, max_length=150)
    customer_reference: Optional[str] = Field(None, max_length=100)

    # Origin
    origin_name: Optional[str] = Field(None, min_length=2, max_length=200)
    origin_address: Optional[str] = Field(None, min_length=5)
    origin_city: Optional[str] = Field(None, min_length=2, max_length=100)
    origin_state: Optional[str] = Field(None, min_length=2, max_length=100)
    origin_postal_code: Optional[str] = Field(None, min_length=3, max_length=20)
    origin_dock_number: Optional[str] = None
    origin_contact_name: Optional[str] = Field(None, min_length=2, max_length=150)
    origin_contact_phone: Optional[str] = Field(None, min_length=7, max_length=30)

    # Destination
    destination_name: Optional[str] = Field(None, min_length=2, max_length=200)
    destination_address: Optional[str] = Field(None, min_length=5)
    destination_city: Optional[str] = Field(None, min_length=2, max_length=100)
    destination_state: Optional[str] = Field(None, min_length=2, max_length=100)
    destination_postal_code: Optional[str] = Field(None, min_length=3, max_length=20)
    destination_dock_number: Optional[str] = None
    destination_contact_name: Optional[str] = Field(None, min_length=2, max_length=150)
    destination_contact_phone: Optional[str] = Field(None, min_length=7, max_length=30)

    # Cargo Details
    goods_description: Optional[str] = Field(None, min_length=3)
    cargo_category: Optional[str] = None
    total_weight_kg: Optional[float] = Field(None, gt=0)
    package_count: Optional[int] = Field(None, gt=0)
    package_unit: Optional[str] = None
    total_volume_cbm: Optional[float] = Field(None, ge=0)
    required_vehicle_type: Optional[str] = None
    is_hazardous: Optional[bool] = None

    # Schedule & Timings
    scheduled_pickup_time: Optional[datetime] = None
    expected_delivery_time: Optional[datetime] = None

    # Priorities & Instructions
    priority: Optional[str] = None
    special_instructions: Optional[str] = None
    invoice_number: Optional[str] = None
    invoice_value: Optional[float] = None


class ShipmentCancelRequest(BaseModel):
    cancellation_reason: str = Field(..., min_length=5, max_length=500, description="Reason for cancelling the shipment")


# ==========================================
# Response Schemas
# ==========================================

class ShipmentEventResponse(BaseModel):
    id: str
    event_type: str
    description: str
    occurred_at: datetime
    location_name: Optional[str] = None
    source: str
    created_by_user_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TransporterBookingSummary(BaseModel):
    id: str
    transporter_id: str
    transporter_name: str
    transporter_code: str
    status: str
    offered_rate: Optional[float] = None
    agreed_rate: Optional[float] = None
    expires_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ShipmentExceptionSummary(BaseModel):
    id: str
    exception_type: str
    severity: str
    status: str
    title: str
    description: str
    reported_at: datetime
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ShipmentAuditLogItem(BaseModel):
    id: str
    action: str
    performed_at: datetime
    user_email: Optional[str] = None
    old_values: Optional[Dict[str, Any]] = None
    new_values: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


class ShipmentListItem(BaseModel):
    id: str
    organization_id: str
    tracking_number: str
    customer_name: Optional[str] = None
    customer_reference: Optional[str] = None
    status: str
    priority: str = "STANDARD"
    origin_name: str
    origin_city: str
    origin_state: str
    destination_name: str
    destination_city: str
    destination_state: str
    scheduled_pickup_time: datetime
    expected_delivery_time: datetime
    actual_pickup_time: Optional[datetime] = None
    actual_delivery_time: Optional[datetime] = None
    total_weight_kg: float
    package_count: int
    package_unit: str = "PALLETS"
    required_vehicle_type: str = "53' Dry Van"
    cargo_category: str = "GENERAL_FREIGHT"
    goods_description: Optional[str] = None
    is_hazardous: bool = False
    assigned_transporter_id: Optional[str] = None
    assigned_transporter_name: Optional[str] = None
    open_exceptions_count: int = 0
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ShipmentDetailResponse(BaseModel):
    id: str
    organization_id: str
    tracking_number: str
    customer_name: Optional[str] = None
    customer_reference: Optional[str] = None
    status: str
    priority: str = "STANDARD"

    # Origin
    origin_name: str
    origin_address: str
    origin_city: str
    origin_state: str
    origin_postal_code: str
    origin_dock_number: Optional[str] = None
    origin_contact_name: str
    origin_contact_phone: str

    # Destination
    destination_name: str
    destination_address: str
    destination_city: str
    destination_state: str
    destination_postal_code: str
    destination_dock_number: Optional[str] = None
    destination_contact_name: str
    destination_contact_phone: str

    # Cargo Specs
    goods_description: str
    cargo_category: str = "GENERAL_FREIGHT"
    total_weight_kg: float
    package_count: int
    package_unit: str = "PALLETS"
    total_volume_cbm: Optional[float] = None
    required_vehicle_type: str = "53' Dry Van"
    is_hazardous: bool = False
    special_instructions: Optional[str] = None
    invoice_number: Optional[str] = None
    invoice_value: Optional[float] = None

    # Timings
    scheduled_pickup_time: datetime
    actual_pickup_time: Optional[datetime] = None
    expected_delivery_time: datetime
    actual_delivery_time: Optional[datetime] = None

    # Transporter & Execution
    assigned_transporter_id: Optional[str] = None
    assigned_transporter_name: Optional[str] = None
    assigned_driver_name: Optional[str] = None
    assigned_vehicle_plate: Optional[str] = None

    # Nested related collections
    bookings: List[TransporterBookingSummary] = []
    events: List[ShipmentEventResponse] = []
    exceptions: List[ShipmentExceptionSummary] = []
    audit_history: List[ShipmentAuditLogItem] = []

    # POD
    pod_verified: bool = False
    pod_signatory_name: Optional[str] = None
    pod_signed_at: Optional[datetime] = None
    pod_document_url: Optional[str] = None

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedShipmentsResponse(BaseModel):
    items: List[ShipmentListItem]
    total: int
    page: int
    page_size: int
    total_pages: int
