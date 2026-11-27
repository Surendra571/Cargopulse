import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class LogisticsAnalyticsOverview(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total_shipments: int = Field(..., description="Total shipments created in the period")
    successful_pickups: int = Field(..., description="Shipments that reached or completed pickup successfully")
    failed_pickups: int = Field(..., description="Shipments that experienced a pickup breach or failure")
    pickup_success_rate: float = Field(..., description="Percentage of attempted pickups that were successful (0-100)")
    on_time_pickup_rate: float = Field(..., description="Percentage of successful pickups on or before scheduled time (0-100)")
    on_time_delivery_rate: float = Field(..., description="Percentage of delivered shipments on or before expected delivery time (0-100)")
    transporter_acceptance_rate: float = Field(..., description="Percentage of booking requests accepted by transporters (0-100)")
    average_pickup_delay_minutes: float = Field(..., description="Average delay in minutes for late pickups")
    average_delivery_delay_minutes: float = Field(..., description="Average delay in minutes for late deliveries")
    average_recovery_time_minutes: float = Field(..., description="Average minutes to resolve recovery workflows")
    pod_completion_rate: float = Field(..., description="Percentage of delivered shipments with submitted Proof of Delivery (0-100)")
    exception_resolution_time_minutes: float = Field(..., description="Average minutes from exception creation to resolution")
    cost_per_shipment: Optional[float] = Field(None, description="Average freight cost per shipment when cost data exists")
    total_cost: float = Field(0.0, description="Sum of freight costs across shipments with cost data")
    cost_shipment_count: int = Field(0, description="Number of shipments with non-zero cost data")
    active_exceptions_count: int = Field(0, description="Currently unresolved exceptions in the period")
    delivered_shipments_count: int = Field(0, description="Shipments successfully marked delivered")
    metric_definitions: Dict[str, str] = Field(default_factory=dict, description="Formal definitions and formulas for all metrics")


class TrendPoint(BaseModel):
    period: str
    bookings_count: int = 0
    acceptance_rate: float = 0.0
    on_time_rate: float = 0.0
    volume: int = 0


class RouteReliabilityMetric(BaseModel):
    origin: str
    destination: str
    lane_name: str
    total_shipments: int
    successful_pickups: int
    pickup_success_rate: float
    on_time_deliveries: int
    on_time_delivery_rate: float
    average_transit_time_hours: float
    average_delay_minutes: float


class TransporterPerformanceMetric(BaseModel):
    transporter_id: uuid.UUID
    transporter_name: str
    transporter_code: Optional[str] = None
    total_bookings: int
    accepted_bookings: int
    rejected_bookings: int
    expired_bookings: int
    acceptance_rate: float
    successful_pickups: int
    failed_pickups: int
    pickup_success_rate: float
    on_time_deliveries: int
    on_time_delivery_rate: float
    performance_trend: List[TrendPoint] = Field(default_factory=list)
    route_reliability: List[RouteReliabilityMetric] = Field(default_factory=list)


class AnalyticsDashboardResponse(BaseModel):
    timeframe: Dict[str, Any]
    overview: LogisticsAnalyticsOverview
    transporters: List[TransporterPerformanceMetric]
    routes: List[RouteReliabilityMetric]
    generated_at: datetime
