import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.auth import User
from app.schemas.transporter import (
    PaginatedTransportersResponse,
    ServiceAreaCreateRequest,
    ServiceAreaResponse,
    TransporterCreateRequest,
    TransporterDetailResponse,
    TransporterDocumentUploadRequest,
    TransporterListItem,
    TransporterUpdateRequest,
    TransporterVerificationRequest,
)
from app.services.transporter_service import TransporterService

router = APIRouter(prefix="/transporters", tags=["Transporter Management"])


@router.post("", response_model=TransporterListItem, status_code=status.HTTP_201_CREATED)
async def create_transporter(
    data: TransporterCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TransporterListItem:
    """
    Registers a new commercial transporter / carrier partner for the organization.
    Initial verification status is REGISTERED.
    """
    return await TransporterService.create_transporter(
        session=db,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        data=data,
    )


@router.get("", response_model=PaginatedTransportersResponse)
async def list_transporters(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Page size"),
    search: Optional[str] = Query(None, description="Search by name, code, contact, phone, or region"),
    verification_status: Optional[str] = Query(None, description="Filter by status (REGISTERED, VERIFIED, SUSPENDED, etc.)"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedTransportersResponse:
    """
    Lists carriers scoped strictly to the current user's organization.
    """
    return await TransporterService.list_transporters(
        session=db,
        organization_id=current_user.organization_id,
        page=page,
        page_size=page_size,
        search=search,
        verification_status=verification_status,
        is_active=is_active,
    )


@router.get("/{transporter_id}", response_model=TransporterDetailResponse)
async def get_transporter(
    transporter_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TransporterDetailResponse:
    """
    Retrieves complete transporter profile with fleet vehicles, drivers, service areas,
    bookings, and reliability statistics. Enforces tenant ownership.
    """
    detail = await TransporterService.get_transporter_detail(
        session=db,
        organization_id=current_user.organization_id,
        transporter_id=transporter_id,
    )
    if not detail:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transporter not found.")
    return detail


@router.put("/{transporter_id}", response_model=TransporterDetailResponse)
async def update_transporter(
    transporter_id: uuid.UUID,
    data: TransporterUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TransporterDetailResponse:
    """
    Updates transporter profile details and operating parameters.
    """
    return await TransporterService.update_transporter(
        session=db,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        transporter_id=transporter_id,
        data=data,
    )


@router.post("/{transporter_id}/verify", response_model=TransporterDetailResponse)
async def verify_transporter(
    transporter_id: uuid.UUID,
    data: TransporterVerificationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TransporterDetailResponse:
    """
    Updates carrier verification lifecycle status.
    Unverified carriers cannot receive active load bookings.
    """
    return await TransporterService.verify_transporter(
        session=db,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        transporter_id=transporter_id,
        data=data,
    )


@router.post("/{transporter_id}/suspend", response_model=TransporterDetailResponse)
async def suspend_transporter(
    transporter_id: uuid.UUID,
    reason: str = Query("Carrier suspended due to operational non-compliance", description="Reason for suspension"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TransporterDetailResponse:
    """
    Suspends carrier account. Suspended carriers cannot accept assignments.
    """
    return await TransporterService.suspend_transporter(
        session=db,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        transporter_id=transporter_id,
        reason=reason,
    )


@router.post("/{transporter_id}/documents", response_model=TransporterDetailResponse)
async def upload_transporter_document(
    transporter_id: uuid.UUID,
    data: TransporterDocumentUploadRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TransporterDetailResponse:
    """
    Uploads compliance document (e.g. MCP, insurance, tax certificates).
    """
    return await TransporterService.upload_transporter_document(
        session=db,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        transporter_id=transporter_id,
        data=data,
    )


@router.post("/{transporter_id}/service-areas", response_model=ServiceAreaResponse)
async def add_service_area(
    transporter_id: uuid.UUID,
    data: ServiceAreaCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ServiceAreaResponse:
    """
    Registers an operating corridor / service area for the carrier.
    """
    return await TransporterService.add_service_area(
        session=db,
        organization_id=current_user.organization_id,
        transporter_id=transporter_id,
        data=data,
    )
