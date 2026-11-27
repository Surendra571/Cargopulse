import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import IntegrationType, OutboxStatus


class NormalizedEvent(BaseModel):
    """
    Standard canonical event representation produced by transporter/ERP adapters.
    """
    event_id: str
    event_type: str  # LOCATION_PING, MILESTONE_UPDATE, ETA_UPDATE, DISPATCH_TRIGGER, INCIDENT_ALERT, CUSTOM
    shipment_id: Optional[str] = None
    tracking_number: Optional[str] = None
    vehicle_id: Optional[str] = None
    vehicle_registration: Optional[str] = None
    driver_phone: Optional[str] = None
    occurred_at: datetime
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location_name: Optional[str] = None
    speed_kmh: Optional[float] = None
    estimated_delivery_at: Optional[datetime] = None
    milestone: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    raw_payload: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class IntegrationConnectionCreate(BaseModel):
    name: str = Field(..., max_length=150)
    slug: Optional[str] = Field(None, max_length=100)
    integration_type: IntegrationType
    adapter_type: str = Field("GENERIC", max_length=100)
    base_url: Optional[str] = Field(None, max_length=500)
    auth_config: Dict[str, Any] = Field(default_factory=dict)
    headers: Dict[str, Any] = Field(default_factory=dict)
    webhook_secret: Optional[str] = Field(None, max_length=255)
    api_key: Optional[str] = Field(None, max_length=255)
    is_active: bool = True


class IntegrationConnectionUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=150)
    slug: Optional[str] = Field(None, max_length=100)
    integration_type: Optional[IntegrationType] = None
    adapter_type: Optional[str] = Field(None, max_length=100)
    base_url: Optional[str] = Field(None, max_length=500)
    auth_config: Optional[Dict[str, Any]] = None
    headers: Optional[Dict[str, Any]] = None
    webhook_secret: Optional[str] = Field(None, max_length=255)
    api_key: Optional[str] = Field(None, max_length=255)
    is_active: Optional[bool] = None


class IntegrationConnectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    slug: Optional[str] = None
    integration_type: IntegrationType
    adapter_type: str
    is_active: bool
    base_url: Optional[str] = None
    webhook_url: Optional[str] = None
    webhook_secret_preview: Optional[str] = None
    api_key_preview: Optional[str] = None
    health_status: str
    consecutive_failures: int
    stats: Dict[str, Any]
    last_synced_at: Optional[datetime] = None
    sync_status: str
    created_at: datetime
    updated_at: datetime


class WebhookEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: Optional[uuid.UUID] = None
    integration_id: Optional[uuid.UUID] = None
    provider: str
    source: str
    event_name: str
    external_event_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    status: str
    retry_count: int
    max_retries: int
    next_retry_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None
    last_attempt_at: Optional[datetime] = None
    error_message: Optional[str] = None
    error_type: Optional[str] = None
    is_dead_letter: bool
    replay_count: int
    last_replayed_at: Optional[datetime] = None
    last_replayed_by_id: Optional[uuid.UUID] = None
    created_at: datetime
    payload: Dict[str, Any]
    normalized_payload: Dict[str, Any]


class OutboxEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    aggregate_type: str
    aggregate_id: uuid.UUID
    event_type: str
    destination: Optional[str] = None
    idempotency_key: Optional[str] = None
    status: OutboxStatus
    retry_count: int
    max_retries: int
    next_retry_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    is_dead_letter: bool
    replay_count: int
    created_at: datetime
    payload: Dict[str, Any]


class IntegrationDashboardMetrics(BaseModel):
    total_webhooks: int
    successful_webhooks: int
    failed_webhooks: int
    pending_webhooks: int
    retry_webhooks: int
    dlq_count: int
    total_outbox: int
    published_outbox: int
    pending_outbox: int
    failed_outbox: int
    system_health: str
    connections_count: int
    healthy_connections_count: int
    recent_errors: List[Dict[str, Any]]


class DLQReplayRequest(BaseModel):
    event_ids: List[uuid.UUID]
    event_source: str = Field("webhook", description="'webhook' or 'outbox'")


class DLQReplayResponse(BaseModel):
    replayed_count: int
    failed_count: int
    details: List[Dict[str, Any]]


class WebhookIngestResponse(BaseModel):
    status: str
    event_id: Optional[str] = None
    message: str
