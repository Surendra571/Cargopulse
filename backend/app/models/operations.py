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
    UniqueConstraint
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin
from app.models.enums import (
    DiscrepancyStatus,
    DiscrepancyType,
    ExceptionSeverity,
    ExceptionStatus,
    ExceptionType,
    PODVerificationStatus,
    ReconciliationStatus,
    RecoveryStatus,
    RecoveryStrategy
)


class ExceptionRecord(Base, TimestampMixin, SoftDeleteMixin):
    """
    Operational exception/incident logged against a shipment (e.g. breakdown, delay, accident).
    """
    __tablename__ = "exceptions"
    __table_args__ = (
        Index("ix_exceptions_shipment_status", "shipment_id", "status"),
        Index("ix_exceptions_org_severity", "organization_id", "severity"),
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
    shipment_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shipments.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    transporter_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transporters.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    priority: Mapped[str] = mapped_column(
        String(20),
        default="MEDIUM",
        nullable=False,
        index=True
    )
    exception_type: Mapped[ExceptionType] = mapped_column(
        SAEnum(ExceptionType, name="exception_type_enum"),
        nullable=False,
        index=True
    )
    severity: Mapped[ExceptionSeverity] = mapped_column(
        SAEnum(ExceptionSeverity, name="exception_severity_enum"),
        default=ExceptionSeverity.MEDIUM,
        nullable=False,
        index=True
    )
    status: Mapped[ExceptionStatus] = mapped_column(
        SAEnum(ExceptionStatus, name="exception_status_enum"),
        default=ExceptionStatus.OPEN,
        nullable=False,
        index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    root_cause: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    escalation_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    escalated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    closure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reported_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    assigned_owner_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    context_data: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict, nullable=False)

    shipment: Mapped[Optional["Shipment"]] = relationship("Shipment", back_populates="exceptions")
    transporter: Mapped[Optional["Transporter"]] = relationship("Transporter")
    assigned_owner: Mapped[Optional["User"]] = relationship("User", foreign_keys=[assigned_owner_id])
    acknowledged_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[acknowledged_by_user_id])
    closed_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[closed_by_user_id])
    recovery_cases: Mapped[List["RecoveryCase"]] = relationship("RecoveryCase", back_populates="exception_record", cascade="all, delete-orphan")


class RecoveryCase(Base, TimestampMixin, SoftDeleteMixin):
    """
    Automated or manual recovery workflow triggered by an exception.
    Coordinates alternative transporters, rescheduling, or expediting.
    """
    __tablename__ = "recovery_cases"
    __table_args__ = (
        Index("ix_recovery_cases_org_status", "organization_id", "status"),
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
    exception_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("exceptions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    case_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    strategy: Mapped[RecoveryStrategy] = mapped_column(
        SAEnum(RecoveryStrategy, name="recovery_strategy_enum"),
        default=RecoveryStrategy.REASSIGN_TRANSPORTER,
        nullable=False
    )
    status: Mapped[RecoveryStatus] = mapped_column(
        SAEnum(RecoveryStatus, name="recovery_status_enum"),
        default=RecoveryStatus.OPEN,
        nullable=False,
        index=True
    )
    proposed_solution: Mapped[str] = mapped_column(Text, nullable=False)
    estimated_cost_impact: Mapped[Optional[Numeric]] = mapped_column(Numeric(12, 2), default=0.0, nullable=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    assigned_to_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    ai_generated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    shipment_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shipments.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    original_transporter_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transporters.id", ondelete="SET NULL"),
        nullable=True
    )
    original_booking_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transporter_bookings.id", ondelete="SET NULL"),
        nullable=True
    )
    replacement_transporter_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transporters.id", ondelete="SET NULL"),
        nullable=True
    )
    replacement_booking_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transporter_bookings.id", ondelete="SET NULL"),
        nullable=True
    )
    approval_status: Mapped[str] = mapped_column(String(50), default="PENDING_APPROVAL", nullable=False)
    approved_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_data: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict, nullable=True)
    alternatives_data: Mapped[Optional[list]] = mapped_column(JSONB, default=list, nullable=True)

    exception_record: Mapped["ExceptionRecord"] = relationship("ExceptionRecord", back_populates="recovery_cases")
    shipment: Mapped[Optional["Shipment"]] = relationship("Shipment")
    original_transporter: Mapped[Optional["Transporter"]] = relationship("Transporter", foreign_keys=[original_transporter_id])
    replacement_transporter: Mapped[Optional["Transporter"]] = relationship("Transporter", foreign_keys=[replacement_transporter_id])
    approved_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[approved_by_user_id])


class ProofOfDelivery(Base, TimestampMixin, SoftDeleteMixin):
    """
    Electronic Proof of Delivery (e-POD) record with signoff, geo-coordinates,
    and digital documents.
    """
    __tablename__ = "proof_of_delivery"
    __table_args__ = (
        UniqueConstraint("shipment_id", name="uq_pod_shipment"),
        Index("ix_pod_org_status", "organization_id", "verification_status"),
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
    signed_by_name: Mapped[str] = mapped_column(String(150), nullable=False)
    signed_by_designation: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    recipient_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    recipient_email: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    signed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    signature_image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    document_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    delivery_photo_urls: Mapped[list] = mapped_column(JSONB, default=list, server_default='[]', nullable=False)
    
    # Quantities & Discrepancies
    expected_quantity: Mapped[int] = mapped_column(Integer, default=0, server_default='0', nullable=False)
    received_quantity: Mapped[int] = mapped_column(Integer, default=0, server_default='0', nullable=False)
    is_shortage: Mapped[bool] = mapped_column(Boolean, default=False, server_default='false', nullable=False)
    shortage_quantity: Mapped[int] = mapped_column(Integer, default=0, server_default='0', nullable=False)
    shortage_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    is_damaged: Mapped[bool] = mapped_column(Boolean, default=False, server_default='false', nullable=False)
    damage_severity: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    damage_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    damage_photo_urls: Mapped[list] = mapped_column(JSONB, default=list, server_default='[]', nullable=False)

    # Driver & Vehicle Information
    driver_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("drivers.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    vehicle_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vehicles.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    driver_name: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    vehicle_plate: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    acknowledgement_type: Mapped[str] = mapped_column(String(50), default="SIGNATURE", server_default="'SIGNATURE'", nullable=False)
    additional_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Location & Geofence Evidence
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    delivery_location_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    distance_to_destination_meters: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_geofence_verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default='false', nullable=False)

    # Verification Lifecycle
    verification_status: Mapped[PODVerificationStatus] = mapped_column(
        SAEnum(PODVerificationStatus, name="pod_verification_status_enum"),
        default=PODVerificationStatus.PENDING,
        nullable=False,
        index=True
    )
    verified_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Audit & File Security
    file_metadata: Mapped[dict] = mapped_column(JSONB, default=dict, server_default='{}', nullable=False)
    submission_history: Mapped[list] = mapped_column(JSONB, default=list, server_default='[]', nullable=False)
    is_modified: Mapped[bool] = mapped_column(Boolean, default=False, server_default='false', nullable=False)

    shipment: Mapped["Shipment"] = relationship("Shipment", back_populates="proof_of_delivery")
    verified_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[verified_by_user_id])
    driver: Mapped[Optional["Driver"]] = relationship("Driver", foreign_keys=[driver_id])
    vehicle: Mapped[Optional["Vehicle"]] = relationship("Vehicle", foreign_keys=[vehicle_id])
    discrepancies: Mapped[List["DeliveryDiscrepancy"]] = relationship("DeliveryDiscrepancy", back_populates="pod", cascade="all, delete-orphan")


class DeliveryDiscrepancy(Base, TimestampMixin, SoftDeleteMixin):
    """
    Detailed discrepancy record noted during POD verification (shortage, damage, rejection).
    """
    __tablename__ = "delivery_discrepancies"
    __table_args__ = (
        Index("ix_discrepancies_org_type", "organization_id", "discrepancy_type"),
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
    pod_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("proof_of_delivery.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    discrepancy_type: Mapped[DiscrepancyType] = mapped_column(
        SAEnum(DiscrepancyType, name="discrepancy_type_enum"),
        nullable=False
    )
    status: Mapped[DiscrepancyStatus] = mapped_column(
        SAEnum(DiscrepancyStatus, name="discrepancy_status_enum"),
        default=DiscrepancyStatus.REPORTED,
        nullable=False
    )
    item_sku: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    item_name: Mapped[str] = mapped_column(String(200), nullable=False)
    expected_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    received_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    claimed_loss_amount: Mapped[Optional[Numeric]] = mapped_column(Numeric(12, 2), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence_image_urls: Mapped[Optional[dict]] = mapped_column(JSONB, default=list, nullable=False)

    pod: Mapped["ProofOfDelivery"] = relationship("ProofOfDelivery", back_populates="discrepancies")


class ReconciliationRecord(Base, TimestampMixin, SoftDeleteMixin):
    """
    Commercial reconciliation between billed freight charges, agreed rates,
    penalties, and POD clearance for manufacturer payments to transporters.
    """
    __tablename__ = "reconciliation_records"
    __table_args__ = (
        UniqueConstraint("shipment_id", name="uq_reconciliation_shipment"),
        Index("ix_reconciliation_org_status", "organization_id", "status"),
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
    base_freight_charge: Mapped[Numeric] = mapped_column(Numeric(12, 2), nullable=False)
    toll_charges: Mapped[Numeric] = mapped_column(Numeric(10, 2), default=0.0, nullable=False)
    detention_charges: Mapped[Numeric] = mapped_column(Numeric(10, 2), default=0.0, nullable=False)
    penalties_deducted: Mapped[Numeric] = mapped_column(Numeric(10, 2), default=0.0, nullable=False)
    discrepancy_deductions: Mapped[Numeric] = mapped_column(Numeric(10, 2), default=0.0, nullable=False)
    final_payable_amount: Mapped[Numeric] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[ReconciliationStatus] = mapped_column(
        SAEnum(ReconciliationStatus, name="reconciliation_status_enum"),
        default=ReconciliationStatus.PENDING,
        nullable=False,
        index=True
    )
    invoice_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    approved_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    total_discrepancies: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    resolved_discrepancies: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    has_mismatches: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_missing_data: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    investigation_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    closed_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    summary_data: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    shipment: Mapped["Shipment"] = relationship("Shipment", back_populates="reconciliation")
    items: Mapped[List["LogisticsReconciliationItem"]] = relationship(
        "LogisticsReconciliationItem", back_populates="reconciliation", cascade="all, delete-orphan"
    )


class LogisticsReconciliationItem(Base, TimestampMixin, SoftDeleteMixin):
    """
    Granular comparison discrepancy item across the 6 reconciliation categories.
    """
    __tablename__ = "logistics_reconciliation_items"
    __table_args__ = (
        Index("ix_reconcil_items_shipment", "shipment_id"),
        Index("ix_reconcil_items_org_status", "organization_id", "status"),
        Index("ix_reconcil_items_category", "category"),
        Index("ix_reconcil_items_assigned", "assigned_user_id"),
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
    reconciliation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reconciliation_records.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="OPEN", nullable=False)  # OPEN, INVESTIGATING, RESOLVED, CLOSED
    expected_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actual_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    discrepancy_delta: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    severity: Mapped[str] = mapped_column(String(50), default="MEDIUM", nullable=False)  # LOW, MEDIUM, HIGH, CRITICAL
    is_matched: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_missing_data: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    assigned_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    investigation_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolved_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    item_metadata: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    reconciliation: Mapped[Optional["ReconciliationRecord"]] = relationship("ReconciliationRecord", back_populates="items")

