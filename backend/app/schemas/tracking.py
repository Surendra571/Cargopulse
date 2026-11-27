import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ShipmentMilestone, TrackingEventSource


class TrackingEventCreateRequest(BaseModel):
    milestone: Optional[ShipmentMilestone] = None
    event_type: Optional[str] = None
    description: Optional[str] = None
    occurred_at: Optional[datetime] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location_name: Optional[str] = None
    source: Optional[TrackingEventSource] = None
    estimated_delivery_at: Optional[datetime] = None
    idempotency_key: Optional[str] = None
    payload: Optional[Dict[str, Any]] = Field(default_factory=dict)


class UpdateETARequest(BaseModel):
    new_eta: datetime
    reason: Optional[str] = None
    location_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    source: Optional[TrackingEventSource] = TrackingEventSource.OPERATOR


class WebhookTrackingEventRequest(BaseModel):
    tracking_number: Optional[str] = None
    shipment_id: Optional[uuid.UUID] = None
    milestone: Optional[str] = None
    event_type: Optional[str] = None
    description: Optional[str] = None
    occurred_at: Optional[datetime] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location_name: Optional[str] = None
    estimated_delivery_at: Optional[datetime] = None
    idempotency_key: Optional[str] = None
    source: Optional[str] = "WEBHOOK"
    payload: Optional[Dict[str, Any]] = Field(default_factory=dict)


class TrackingEventResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    shipment_id: uuid.UUID
    event_type: str
    milestone: Optional[str] = None
    description: str
    occurred_at: datetime
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location_name: Optional[str] = None
    source: str
    idempotency_key: Optional[str] = None
    estimated_delivery_at: Optional[datetime] = None
    created_by_user_id: Optional[uuid.UUID] = None
    payload: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


class MilestoneProgressItem(BaseModel):
    milestone: str
    label: str
    completed: bool
    occurred_at: Optional[datetime] = None
    location_name: Optional[str] = None
    is_current: bool = False


class ShipmentLocationSummary(BaseModel):
    name: str
    city: str
    state: str
    postal_code: str
    dock_number: Optional[str] = None
    contact_name: str
    contact_phone: str


class ShipmentTimelineResponse(BaseModel):
    shipment_id: uuid.UUID
    tracking_number: str
    status: str
    current_milestone: Optional[str] = None
    scheduled_pickup_time: datetime
    actual_pickup_time: Optional[datetime] = None
    expected_delivery_time: datetime
    actual_delivery_time: Optional[datetime] = None
    is_tracking_stale: bool = False
    last_tracking_event_at: Optional[datetime] = None
    last_known_location: Optional[str] = None
    last_known_latitude: Optional[float] = None
    last_known_longitude: Optional[float] = None
    eta_delay_minutes: int = 0
    total_weight_kg: float
    goods_description: str
    origin: ShipmentLocationSummary
    destination: ShipmentLocationSummary
    transporter: Optional[Dict[str, Any]] = None
    assigned_vehicle: Optional[Dict[str, Any]] = None
    assigned_driver: Optional[Dict[str, Any]] = None
    events: List[TrackingEventResponse] = Field(default_factory=list)
    milestone_progress: List[MilestoneProgressItem] = Field(default_factory=list)


class TrackingScanResponse(BaseModel):
    scanned_count: int
    stale_flagged_count: int
    exceptions_created: int
    simulated_now: str
