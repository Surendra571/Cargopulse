import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import DiscrepancyStatus, DiscrepancyType, PODVerificationStatus


class StoredFileSummary(BaseModel):
    file_key: str
    file_name: str
    content_type: str
    file_size_bytes: int
    sha256_hash: str
    storage_provider: str
    url: str
    uploaded_at: str
    category: str


class PODUploadResponse(BaseModel):
    success: bool = True
    file: StoredFileSummary


class DiscrepancyItemResponse(BaseModel):
    id: str
    pod_id: str
    discrepancy_type: str
    status: str
    item_name: str
    expected_quantity: int
    received_quantity: int
    variance: int
    notes: Optional[str] = None
    evidence_image_urls: List[str] = []

    model_config = ConfigDict(from_attributes=True)


class DriverPODSubmissionRequest(BaseModel):
    """
    Payload submitted by driver (or carrier) at consignee drop-off.
    """
    recipient_name: str = Field(..., min_length=2, max_length=150, description="Name of person accepting delivery")
    recipient_designation: Optional[str] = Field(None, max_length=100)
    recipient_phone: Optional[str] = Field(None, max_length=50)
    recipient_email: Optional[str] = Field(None, max_length=150)
    delivered_at: Optional[datetime] = None
    
    received_quantity: int = Field(..., ge=0, description="Actual quantity of cargo/packages received")
    acknowledgement_type: str = Field("SIGNATURE", description="Method of acknowledgement: SIGNATURE, OTP_VERIFIED, etc.")
    
    # Evidence & Signoff
    signature_image_url: Optional[str] = None
    document_url: Optional[str] = None
    delivery_photo_urls: List[str] = Field(default_factory=list, description="Photos of cargo delivered at loading dock / customer site")
    
    # Location & Geofence
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    delivery_location_name: Optional[str] = None
    
    # Damage Reporting
    is_damaged: bool = False
    damage_severity: Optional[str] = Field(None, description="MINOR, MODERATE, SEVERE, TOTAL_LOSS")
    damage_description: Optional[str] = None
    damage_photo_urls: List[str] = Field(default_factory=list, description="Photographic proof of package/cargo damage")
    
    # Shortage / Discrepancy
    shortage_description: Optional[str] = None
    
    additional_notes: Optional[str] = None


class ManufacturerPODReviewRequest(BaseModel):
    """
    Review action taken by manufacturer / receiving facility on submitted POD.
    """
    action: str = Field(..., pattern="^(APPROVE|REJECT|FLAG_DISCREPANCY)$")
    rejection_reason: Optional[str] = Field(None, max_length=1000)
    notes: Optional[str] = Field(None, max_length=1000)


class ProofOfDeliveryResponse(BaseModel):
    id: str
    organization_id: str
    shipment_id: str
    tracking_number: Optional[str] = None
    verification_status: str
    
    signed_by_name: str
    signed_by_designation: Optional[str] = None
    recipient_phone: Optional[str] = None
    recipient_email: Optional[str] = None
    signed_at: datetime
    
    expected_quantity: int
    received_quantity: int
    is_shortage: bool
    shortage_quantity: int
    shortage_description: Optional[str] = None
    
    is_damaged: bool
    damage_severity: Optional[str] = None
    damage_description: Optional[str] = None
    damage_photo_urls: List[str] = []
    
    signature_image_url: Optional[str] = None
    document_url: Optional[str] = None
    delivery_photo_urls: List[str] = []
    
    driver_id: Optional[str] = None
    vehicle_id: Optional[str] = None
    driver_name: Optional[str] = None
    vehicle_plate: Optional[str] = None
    acknowledgement_type: str
    additional_notes: Optional[str] = None
    
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    delivery_location_name: Optional[str] = None
    distance_to_destination_meters: Optional[float] = None
    is_geofence_verified: bool
    
    verified_at: Optional[datetime] = None
    verified_by_user_id: Optional[str] = None
    rejection_reason: Optional[str] = None
    
    file_metadata: Dict[str, Any] = {}
    submission_history: List[Dict[str, Any]] = []
    discrepancies: List[DiscrepancyItemResponse] = []
    is_modified: bool
    
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PODListResponse(BaseModel):
    items: List[ProofOfDeliveryResponse]
    total: int
    page: int
    page_size: int
    pages: int
