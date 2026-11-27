import uuid
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin
from app.models.enums import (
    AssignmentStatus,
    BookingStatus,
    CommitmentStatus,
    ShipmentStatus
)


class Shipment(Base, TimestampMixin, SoftDeleteMixin):
    """
    Core logistics shipment created by a manufacturer or 3PL.
    """
    __tablename__ = "shipments"
    __table_args__ = (
        UniqueConstraint("organization_id", "tracking_number", name="uq_shipments_org_tracking"),
        Index("ix_shipments_org_status", "organization_id", "status"),
        Index("ix_shipments_pickup_window", "organization_id", "scheduled_pickup_time"),
        Index("ix_shipments_delivery_window", "organization_id", "expected_delivery_time"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    tracking_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[ShipmentStatus] = mapped_column(
        SAEnum(ShipmentStatus, name="shipment_status_enum"),
        default=ShipmentStatus.DRAFT,
        nullable=False,
        index=True
    )

    # Origin details
    origin_name: Mapped[str] = mapped_column(String(200), nullable=False)
    origin_address: Mapped[str] = mapped_column(Text, nullable=False)
    origin_city: Mapped[str] = mapped_column(String(100), nullable=False)
    origin_state: Mapped[str] = mapped_column(String(100), nullable=False)
    origin_postal_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    origin_dock_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    origin_contact_name: Mapped[str] = mapped_column(String(150), nullable=False)
    origin_contact_phone: Mapped[str] = mapped_column(String(30), nullable=False)

    # Destination details
    destination_name: Mapped[str] = mapped_column(String(200), nullable=False)
    destination_address: Mapped[Text] = mapped_column(Text, nullable=False)
    destination_city: Mapped[str] = mapped_column(String(100), nullable=False)
    destination_state: Mapped[str] = mapped_column(String(100), nullable=False)
    destination_postal_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    destination_dock_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    destination_contact_name: Mapped[str] = mapped_column(String(150), nullable=False)
    destination_contact_phone: Mapped[str] = mapped_column(String(30), nullable=False)

    # Timings
    scheduled_pickup_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actual_pickup_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expected_delivery_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actual_delivery_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Cargo Specs
    total_weight_kg: Mapped[Numeric] = mapped_column(Numeric(12, 2), nullable=False)
    total_volume_cbm: Mapped[Optional[Numeric]] = mapped_column(Numeric(10, 2), nullable=True)
    package_count: Mapped[int] = mapped_column(Integer, nullable=False)
    goods_description: Mapped[str] = mapped_column(Text, nullable=False)
    is_hazardous: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    invoice_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    invoice_value: Mapped[Optional[Numeric]] = mapped_column(Numeric(14, 2), nullable=True)

    # Tracking & Live Milestones
    current_milestone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    last_tracking_event_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    last_known_location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_known_latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    last_known_longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_tracking_stale: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    eta_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    eta_delay_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Metadata & flexible item details
    items_manifest: Mapped[Optional[dict]] = mapped_column(JSONB, default=list, nullable=False)
    custom_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict, nullable=False)

    # Relationships
    bookings: Mapped[List["TransporterBooking"]] = relationship("TransporterBooking", back_populates="shipment", cascade="all, delete-orphan")
    assignments: Mapped[List["ShipmentAssignment"]] = relationship("ShipmentAssignment", back_populates="shipment", cascade="all, delete-orphan")
    events: Mapped[List["ShipmentEvent"]] = relationship("ShipmentEvent", back_populates="shipment", cascade="all, delete-orphan", order_by="ShipmentEvent.occurred_at")
    commitments: Mapped[List["PickupCommitment"]] = relationship("PickupCommitment", back_populates="shipment", cascade="all, delete-orphan")
    exceptions: Mapped[List["ExceptionRecord"]] = relationship("ExceptionRecord", back_populates="shipment", cascade="all, delete-orphan")
    proof_of_delivery: Mapped[Optional["ProofOfDelivery"]] = relationship("ProofOfDelivery", back_populates="shipment", uselist=False, cascade="all, delete-orphan")
    reconciliation: Mapped[Optional["ReconciliationRecord"]] = relationship("ReconciliationRecord", back_populates="shipment", uselist=False)


class TransporterBooking(Base, TimestampMixin, SoftDeleteMixin):
    """
    Booking / tender offer to a transporter for a shipment.
    """
    __tablename__ = "transporter_bookings"
    __table_args__ = (
        Index("ix_bookings_shipment_transporter", "shipment_id", "transporter_id"),
        Index("ix_bookings_org_status", "organization_id", "status"),
        Index("ix_bookings_reference", "booking_reference"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    shipment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shipments.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    transporter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transporters.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    booking_reference: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, index=True
    )
    status: Mapped[BookingStatus] = mapped_column(
        SAEnum(BookingStatus, name="booking_status_enum"),
        default=BookingStatus.REQUESTED,
        nullable=False,
        index=True
    )
    offered_rate: Mapped[Optional[Numeric]] = mapped_column(Numeric(12, 2), nullable=True)
    agreed_rate: Mapped[Optional[Numeric]] = mapped_column(Numeric(12, 2), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    response_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    responded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    vehicle_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vehicles.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    driver_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("drivers.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    booking_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict, nullable=False)

    shipment: Mapped["Shipment"] = relationship("Shipment", back_populates="bookings")
    transporter: Mapped["Transporter"] = relationship("Transporter", back_populates="bookings")
    vehicle: Mapped[Optional["Vehicle"]] = relationship("Vehicle")
    driver: Mapped[Optional["Driver"]] = relationship("Driver")


class ShipmentAssignment(Base, TimestampMixin, SoftDeleteMixin):
    """
    Active or historical assignment of vehicle and driver to a shipment.
    Enforces that only one active assignment exists per shipment.
    """
    __tablename__ = "shipment_assignments"
    __table_args__ = (
        Index("ix_assignments_shipment_status", "shipment_id", "status"),
        Index(
            "uq_active_assignment_per_shipment",
            "shipment_id",
            unique=True,
            postgresql_where=text("status IN ('ASSIGNED', 'ACCEPTED') AND is_deleted = false")
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    shipment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shipments.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    vehicle_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vehicles.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    driver_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("drivers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    status: Mapped[AssignmentStatus] = mapped_column(
        SAEnum(AssignmentStatus, name="assignment_status_enum"),
        default=AssignmentStatus.ASSIGNED,
        nullable=False
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    cancelled_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    shipment: Mapped["Shipment"] = relationship("Shipment", back_populates="assignments")
    vehicle: Mapped["Vehicle"] = relationship("Vehicle", back_populates="assignments")
    driver: Mapped["Driver"] = relationship("Driver", back_populates="assignments")


class ShipmentEvent(Base):
    """
    Immutable, append-only event log capturing every lifecycle transition,
    telematics ping, and operational milestone.
    """
    __tablename__ = "shipment_events"
    __table_args__ = (
        Index("ix_shipment_events_shipment_time", "shipment_id", "occurred_at"),
        Index("ix_shipment_events_org_type", "organization_id", "event_type"),
        Index("ix_shipment_events_milestone", "milestone"),
        Index("ix_shipment_events_idempotency", "shipment_id", "idempotency_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    shipment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shipments.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    milestone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    location_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source: Mapped[str] = mapped_column(String(50), default="SYSTEM", nullable=False)  # TRANSPORTER, DRIVER, OPERATOR, WEBHOOK, SYSTEM, TELEMATICS
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    estimated_delivery_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    payload: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict, nullable=False)

    shipment: Mapped["Shipment"] = relationship("Shipment", back_populates="events")


class PickupCommitment(Base, TimestampMixin, SoftDeleteMixin):
    """
    Transporter's pickup SLA commitment with dock time slot.
    Tracks punctuality, breach detection, and accountability.
    """
    __tablename__ = "pickup_commitments"
    __table_args__ = (
        Index("ix_commitments_shipment_status", "shipment_id", "status"),
        Index("ix_commitments_committed_slot", "committed_pickup_slot_start", "committed_pickup_slot_end"),
        Index("ix_pickup_commitments_deadline_status", "pickup_deadline", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    shipment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shipments.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    transporter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transporters.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    booking_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transporter_bookings.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    committed_pickup_slot_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    committed_pickup_slot_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    pickup_deadline: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    expected_arrival: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    assigned_vehicle_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vehicles.id", ondelete="SET NULL"),
        nullable=True
    )
    assigned_driver_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("drivers.id", ondelete="SET NULL"),
        nullable=True
    )
    status: Mapped[CommitmentStatus] = mapped_column(
        SAEnum(CommitmentStatus, name="commitment_status_enum"),
        default=CommitmentStatus.PENDING,
        nullable=False,
        index=True
    )
    actual_arrival_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_breached: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    breach_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    penalties_incurred: Mapped[Optional[Numeric]] = mapped_column(Numeric(10, 2), default=0.0, nullable=False)
    commitment_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict, nullable=True)

    shipment: Mapped["Shipment"] = relationship("Shipment", back_populates="commitments")
    transporter: Mapped["Transporter"] = relationship("Transporter")
    booking: Mapped[Optional["TransporterBooking"]] = relationship("TransporterBooking")
    vehicle: Mapped[Optional["Vehicle"]] = relationship("Vehicle")
    driver: Mapped[Optional["Driver"]] = relationship("Driver")
