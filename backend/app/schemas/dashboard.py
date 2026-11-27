from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict


# ==========================================
# KPI Metrics
# ==========================================

class DashboardMetricsResponse(BaseModel):
    total_shipments: int
    pending_pickups: int
    confirmed_bookings: int
    pickups_at_risk: int
    failed_pickups: int
    in_transit_shipments: int
    delayed_deliveries: int
    delivered_shipments: int
    open_exceptions: int
    pickup_success_rate: float  # Percentage (e.g. 98.5)
    on_time_delivery_rate: float  # Percentage (e.g. 96.2)

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# Visualizations
# ==========================================

class VolumeOverTimePoint(BaseModel):
    date: str  # YYYY-MM-DD
    total_shipments: int
    delivered: int
    exceptions: int


class PickupPerformanceBreakdown(BaseModel):
    total_commitments: int
    on_time: int
    delayed: int
    failed: int
    success_rate: float


class DeliveryPerformanceBreakdown(BaseModel):
    total_deliveries: int
    on_time: int
    delayed: int
    on_time_rate: float


class TransporterReliabilityItem(BaseModel):
    transporter_id: str
    transporter_name: str
    transporter_code: str
    total_shipments: int
    on_time_pickups: int
    on_time_deliveries: int
    reliability_score: float
    active_exceptions: int


class ExceptionDistributionItem(BaseModel):
    category: str
    count: int
    percentage: float


class RecentActivityItem(BaseModel):
    id: str
    shipment_id: str
    tracking_number: str
    event_type: str
    description: str
    occurred_at: datetime
    location_name: Optional[str] = None
    source: str


# ==========================================
# Complete Dashboard Bundle
# ==========================================

class DashboardOverviewResponse(BaseModel):
    metrics: DashboardMetricsResponse
    volume_over_time: List[VolumeOverTimePoint]
    pickup_performance: PickupPerformanceBreakdown
    delivery_performance: DeliveryPerformanceBreakdown
    transporter_rankings: List[TransporterReliabilityItem]
    exceptions_by_type: List[ExceptionDistributionItem]
    exceptions_by_severity: List[ExceptionDistributionItem]
    recent_activity: List[RecentActivityItem]

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# Dashboard Tables / Shipments
# ==========================================

class DashboardShipmentItem(BaseModel):
    id: str
    tracking_number: str
    status: str
    origin_city: str
    origin_state: str
    destination_city: str
    destination_state: str
    transporter_id: Optional[str] = None
    transporter_name: Optional[str] = None
    scheduled_pickup_time: datetime
    expected_delivery_time: datetime
    actual_pickup_time: Optional[datetime] = None
    actual_delivery_time: Optional[datetime] = None
    total_weight_kg: float
    package_count: int
    is_at_risk: bool = False
    open_exceptions_count: int = 0
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DashboardExceptionItem(BaseModel):
    id: str
    shipment_id: str
    tracking_number: str
    exception_type: str
    severity: str
    status: str
    title: str
    description: str
    reported_at: datetime
    transporter_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class PaginatedShipmentsResponse(BaseModel):
    items: List[DashboardShipmentItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class PaginatedExceptionsResponse(BaseModel):
    items: List[DashboardExceptionItem]
    total: int
    page: int
    page_size: int
    total_pages: int


# ==========================================
# Detailed Shipment View
# ==========================================

class ShipmentEventItem(BaseModel):
    id: str
    event_type: str
    description: str
    occurred_at: datetime
    location_name: Optional[str] = None
    source: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class ShipmentDetailResponse(BaseModel):
    id: str
    tracking_number: str
    status: str
    origin_name: str
    origin_address: str
    origin_city: str
    origin_state: str
    origin_contact_name: str
    origin_contact_phone: str
    destination_name: str
    destination_address: str
    destination_city: str
    destination_state: str
    destination_contact_name: str
    destination_contact_phone: str
    scheduled_pickup_time: datetime
    actual_pickup_time: Optional[datetime] = None
    expected_delivery_time: datetime
    actual_delivery_time: Optional[datetime] = None
    total_weight_kg: float
    package_count: int
    goods_description: str
    is_hazardous: bool
    transporter_id: Optional[str] = None
    transporter_name: Optional[str] = None
    driver_name: Optional[str] = None
    vehicle_plate: Optional[str] = None
    events: List[ShipmentEventItem] = []
    exceptions: List[DashboardExceptionItem] = []
    pod_verified: bool = False
    pod_signatory_name: Optional[str] = None
    pod_verified_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

