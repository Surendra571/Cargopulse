import uuid
from datetime import datetime
from typing import List, Optional
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin


class Transporter(Base, TimestampMixin, SoftDeleteMixin):
    """
    Transporter / Carrier entity partnering with or managed by an organization.
    """
    __tablename__ = "transporters"
    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_transporters_org_code"),
        Index("ix_transporters_org_status", "organization_id", "is_active"),
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
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    contact_person: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    phone: Mapped[str] = mapped_column(String(30), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    gstin: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    reliability_score: Mapped[float] = mapped_column(Float, default=100.0, nullable=False)
    total_deliveries: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    on_time_deliveries: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    compliance_details: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict, nullable=False)

    # Relationships
    vehicles: Mapped[List["Vehicle"]] = relationship("Vehicle", back_populates="transporter", cascade="all, delete-orphan")
    drivers: Mapped[List["Driver"]] = relationship("Driver", back_populates="transporter", cascade="all, delete-orphan")
    service_areas: Mapped[List["TransporterServiceArea"]] = relationship("TransporterServiceArea", back_populates="transporter", cascade="all, delete-orphan")
    bookings: Mapped[List["TransporterBooking"]] = relationship("TransporterBooking", back_populates="transporter")


class Vehicle(Base, TimestampMixin, SoftDeleteMixin):
    """
    Fleet vehicle registered under a transporter.
    """
    __tablename__ = "vehicles"
    __table_args__ = (
        UniqueConstraint("organization_id", "license_plate", name="uq_vehicles_org_plate"),
        Index("ix_vehicles_org_type", "organization_id", "vehicle_type"),
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
    transporter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transporters.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    license_plate: Mapped[str] = mapped_column(String(50), nullable=False)
    vehicle_type: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., 32FT MXL, 20FT CONTAINER, 14FT FLATBED
    capacity_kg: Mapped[Numeric] = mapped_column(Numeric(12, 2), nullable=False)
    volume_cbm: Mapped[Optional[Numeric]] = mapped_column(Numeric(10, 2), nullable=True)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    rc_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    insurance_expiry: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    fitness_expiry: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    telematics_device_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    transporter: Mapped["Transporter"] = relationship("Transporter", back_populates="vehicles")
    assignments: Mapped[List["ShipmentAssignment"]] = relationship("ShipmentAssignment", back_populates="vehicle")


class Driver(Base, TimestampMixin, SoftDeleteMixin):
    """
    Commercial driver registered under a transporter.
    """
    __tablename__ = "drivers"
    __table_args__ = (
        UniqueConstraint("organization_id", "phone", name="uq_drivers_org_phone"),
        Index("ix_drivers_org_status", "organization_id", "is_available"),
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
    transporter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transporters.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str] = mapped_column(String(30), nullable=False)
    license_number: Mapped[str] = mapped_column(String(50), nullable=False)
    license_expiry: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )

    transporter: Mapped["Transporter"] = relationship("Transporter", back_populates="drivers")
    assignments: Mapped[List["ShipmentAssignment"]] = relationship("ShipmentAssignment", back_populates="driver")


class TransporterServiceArea(Base, TimestampMixin):
    """
    Geographic lane / service coverage for transporters (origin-destination pin codes or zones).
    """
    __tablename__ = "transporter_service_areas"
    __table_args__ = (
        Index("ix_transporter_lanes", "origin_region", "destination_region"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    transporter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transporters.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    origin_region: Mapped[str] = mapped_column(String(100), nullable=False)  # State, Region, or City
    destination_region: Mapped[str] = mapped_column(String(100), nullable=False)
    origin_postal_code_prefix: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    destination_postal_code_prefix: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    estimated_transit_hours: Mapped[int] = mapped_column(Integer, default=24, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    transporter: Mapped["Transporter"] = relationship("Transporter", back_populates="service_areas")


class OrganizationTransporter(Base, TimestampMixin):
    """
    Many-to-many partnership linking a manufacturer organization to a transporter.
    Allows a single carrier/transporter to be associated with multiple manufacturers
    without duplicating the transporter, vehicle, or driver records.
    """
    __tablename__ = "organization_transporters"
    __table_args__ = (
        UniqueConstraint("organization_id", "transporter_id", name="uq_org_transporter"),
        Index("ix_org_transporters_status", "organization_id", "status"),
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
    transporter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transporters.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    status: Mapped[str] = mapped_column(String(50), default="ACTIVE", nullable=False)  # ACTIVE, PENDING, SUSPENDED
    contract_reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    custom_rates: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict, nullable=False)

    transporter: Mapped["Transporter"] = relationship("Transporter")
