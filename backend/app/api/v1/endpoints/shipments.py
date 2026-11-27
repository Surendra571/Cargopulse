import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.auth import User
from app.schemas.shipment import (
    PaginatedShipmentsResponse,
    ShipmentCancelRequest,
    ShipmentCreateRequest,
    ShipmentDetailResponse,
    ShipmentUpdateRequest,
)
from app.services.shipment_service import ShipmentService

router = APIRouter(prefix="/shipments", tags=["Shipment Management"])


@router.post("", response_model=ShipmentDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_shipment(
    data: ShipmentCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ShipmentDetailResponse:
    """
    Creates a new freight shipment for the authenticated tenant.
    Enforces business rules (positive weight, deadline validation), generates a
    human-readable tracking number, and logs creation in immutable event & audit trails.
    """
    return await ShipmentService.create_shipment(
        session=db,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        data=data,
    )


@router.get("", response_model=PaginatedShipmentsResponse)
async def list_shipments(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Page size"),
    search: Optional[str] = Query(None, description="Search by tracking number, customer, city, or goods"),
    status: Optional[str] = Query(None, description="Filter by shipment status"),
    priority: Optional[str] = Query(None, description="Filter by priority (STANDARD, EXPEDITED, CRITICAL)"),
    start_date: Optional[datetime] = Query(None, description="Filter created after"),
    end_date: Optional[datetime] = Query(None, description="Filter created before"),
    sort_by: str = Query("created_at", description="Field to sort by"),
    sort_order: str = Query("desc", description="Sort order (asc or desc)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedShipmentsResponse:
    """
    Lists shipments scoped strictly to the current user's organization.
    Supports multi-criteria filtering, search, and pagination.
    """
    return await ShipmentService.list_shipments(
        session=db,
        organization_id=current_user.organization_id,
        page=page,
        page_size=page_size,
        search=search,
        status_filter=status,
        priority_filter=priority,
        start_date=start_date,
        end_date=end_date,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get("/{shipment_id}", response_model=ShipmentDetailResponse)
async def get_shipment(
    shipment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ShipmentDetailResponse:
    """
    Retrieves full details for a shipment, including carrier bookings,
    milestone events, exceptions, audit log history, and proof of delivery.
    Enforces tenant ownership.
    """
    detail = await ShipmentService.get_shipment_detail(
        session=db,
        organization_id=current_user.organization_id,
        shipment_id=shipment_id,
    )
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shipment not found or unauthorized.",
        )
    return detail


@router.put("/{shipment_id}", response_model=ShipmentDetailResponse)
async def update_shipment(
    shipment_id: uuid.UUID,
    data: ShipmentUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ShipmentDetailResponse:
    """
    Updates eligible shipment details.
    Prevents updating cancelled shipments or changing core routing/cargo specs after dispatch.
    Records changes in audit trail.
    """
    return await ShipmentService.update_shipment(
        session=db,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        shipment_id=shipment_id,
        data=data,
    )


@router.post("/{shipment_id}/cancel", response_model=ShipmentDetailResponse)
async def cancel_shipment(
    shipment_id: uuid.UUID,
    data: ShipmentCancelRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ShipmentDetailResponse:
    """
    Cancels a shipment, invalidates active transporter tenders, and records
    the cancellation reason in immutable events & audit logs.
    Delivered shipments cannot be cancelled.
    """
    return await ShipmentService.cancel_shipment(
        session=db,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        shipment_id=shipment_id,
        data=data,
    )
