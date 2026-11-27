import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.auth import User
from app.schemas.transporter import (
    PaginatedVehiclesResponse,
    VehicleCreateRequest,
    VehicleListItem,
    VehicleUpdateRequest,
)
from app.services.transporter_service import TransporterService

router = APIRouter(prefix="/vehicles", tags=["Vehicle Fleet Management"])


@router.post("", response_model=VehicleListItem, status_code=status.HTTP_201_CREATED)
async def create_vehicle(
    data: VehicleCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VehicleListItem:
    """
    Registers a new commercial fleet vehicle under an authorized carrier partner.
    Enforces unique license plate within the organization and positive capacity.
    """
    return await TransporterService.create_vehicle(
        session=db,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        data=data,
    )


@router.get("", response_model=PaginatedVehiclesResponse)
async def list_vehicles(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Page size"),
    transporter_id: Optional[uuid.UUID] = Query(None, description="Filter by carrier"),
    search: Optional[str] = Query(None, description="Search by license plate, type, RC number, device, or carrier"),
    vehicle_type: Optional[str] = Query(None, description="Filter by vehicle type"),
    is_available: Optional[bool] = Query(None, description="Filter by availability"),
    has_expired_docs: Optional[bool] = Query(None, description="Filter by expired insurance/fitness status"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedVehiclesResponse:
    """
    Lists commercial vehicles across all partnered carriers with document expiry status.
    """
    return await TransporterService.list_vehicles(
        session=db,
        organization_id=current_user.organization_id,
        transporter_id=transporter_id,
        page=page,
        page_size=page_size,
        search=search,
        vehicle_type=vehicle_type,
        is_available=is_available,
        has_expired_docs=has_expired_docs,
    )


@router.put("/{vehicle_id}", response_model=VehicleListItem)
async def update_vehicle(
    vehicle_id: uuid.UUID,
    data: VehicleUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VehicleListItem:
    """
    Updates vehicle specifications, equipment types, insurance, or availability.
    """
    return await TransporterService.update_vehicle(
        session=db,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        vehicle_id=vehicle_id,
        data=data,
    )


@router.delete("/{vehicle_id}")
async def delete_vehicle(
    vehicle_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Soft deletes a vehicle record from the active fleet.
    """
    return await TransporterService.delete_vehicle(
        session=db,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        vehicle_id=vehicle_id,
    )
