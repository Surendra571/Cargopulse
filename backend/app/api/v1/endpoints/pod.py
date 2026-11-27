import logging
import uuid
from typing import Any, Dict, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.auth import User
from app.schemas.pod import (
    DriverPODSubmissionRequest,
    ManufacturerPODReviewRequest,
    PODListResponse,
    PODUploadResponse,
    ProofOfDeliveryResponse,
    StoredFileSummary,
)
from app.services.pod_service import pod_service
from app.services.storage_service import storage_service

logger = logging.getLogger("cargopulse.api.pod")

router = APIRouter(prefix="/pod", tags=["proof-of-delivery"])


@router.post("/upload", response_model=PODUploadResponse)
async def upload_pod_evidence_file(
    shipment_id: uuid.UUID = Form(...),
    category: str = Form("delivery_photo"),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Secure file upload endpoint for proof of delivery evidence (delivery photos,
    recipient signatures, damage evidence, signed BOL documents).
    Validates MIME type, limits file size to 10MB, stores in S3/object storage,
    and returns a controlled-access URL.
    """
    file_bytes = await file.read()
    content_type = file.content_type or "application/octet-stream"

    meta = await storage_service.upload_file_bytes(
        data=file_bytes,
        file_name=file.filename or "evidence.jpg",
        content_type=content_type,
        organization_id=current_user.organization_id,
        shipment_id=shipment_id,
        category=category,
    )

    return PODUploadResponse(
        success=True,
        file=StoredFileSummary(**meta),
    )


@router.get("/files/download")
async def download_pod_file(
    file_key: str = Query(...),
    expires: Optional[int] = Query(None),
    token: Optional[str] = Query(None),
):
    """
    Controlled-access download endpoint for local/private storage objects.
    Enforces HMAC expiration token verification.
    """
    if expires and token:
        valid = storage_service.verify_hmac_token(file_key, expires, token)
        if not valid:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Controlled-access URL has expired or has an invalid token.",
            )

    data, content_type = storage_service.get_file_bytes(file_key)
    return Response(
        content=data,
        media_type=content_type,
        headers={
            "Cache-Control": "private, max-age=3600",
            "Content-Disposition": f'inline; filename="{file_key.split("/")[-1]}"',
        },
    )


@router.post("/shipments/{shipment_id}/submit", response_model=ProofOfDeliveryResponse)
async def submit_proof_of_delivery(
    shipment_id: uuid.UUID,
    payload: DriverPODSubmissionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Driver submission of digital proof of delivery:
    - Enforces assigned driver or transporter authorization
    - Validates mandatory recipient acknowledgement and photographic evidence
    - Automatically creates shortage / damage discrepancies and operational exceptions
    - Updates shipment status to DELIVERED and records audit trail
    """
    return await pod_service.submit_pod(
        session=db,
        shipment_id=shipment_id,
        req=payload,
        current_user=current_user,
    )


@router.post("/shipments/{shipment_id}/review", response_model=ProofOfDeliveryResponse)
async def review_proof_of_delivery(
    shipment_id: uuid.UUID,
    payload: ManufacturerPODReviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Manufacturer review & verification on submitted proof of delivery.
    Supports APPROVE, REJECT (with mandatory reason), or FLAG_DISCREPANCY.
    """
    return await pod_service.review_pod(
        session=db,
        shipment_id=shipment_id,
        req=payload,
        current_user=current_user,
    )


@router.get("/shipments/{shipment_id}", response_model=ProofOfDeliveryResponse)
async def get_shipment_pod(
    shipment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieves the complete ePOD record for a shipment, including evidence photo gallery,
    discrepancy reports, and full revision audit history.
    """
    return await pod_service.get_pod_by_shipment(
        session=db,
        shipment_id=shipment_id,
        organization_id=current_user.organization_id,
    )


@router.get("", response_model=PODListResponse)
async def list_proof_of_deliveries(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    is_damaged: Optional[bool] = Query(None),
    is_shortage: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Lists proof of delivery records for the manufacturer operations portal with
    verification status filters, discrepancy indicators, search, and pagination.
    """
    return await pod_service.list_pods(
        session=db,
        organization_id=current_user.organization_id,
        page=page,
        page_size=page_size,
        status_filter=status_filter,
        search=search,
        is_damaged=is_damaged,
        is_shortage=is_shortage,
    )
