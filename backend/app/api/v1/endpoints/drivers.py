import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.auth import User
from app.schemas.transporter import (
    DriverAssignmentRequest,
    DriverCreateRequest,
    DriverListItem,
    DriverUpdateRequest,
    PaginatedDriversResponse,
)
from app.services.transporter_service import TransporterService

router = APIRouter(prefix="/drivers", tags=["Driver Management"])


@router.post("", response_model=DriverListItem, status_code=status.HTTP_201_CREATED)
async def create_driver(
    data: DriverCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DriverListItem:
    """
    Registers a new commercial driver under an authorized carrier partner.
    Protects driver privacy by masking license numbers in standard responses.
    """
    return await TransporterService.create_driver(
        session=db,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        data=data,
    )


@router.get("", response_model=PaginatedDriversResponse)
async def list_drivers(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Page size"),
    transporter_id: Optional[uuid.UUID] = Query(None, description="Filter by carrier"),
    search: Optional[str] = Query(None, description="Search by name, phone, license, or carrier"),
    is_available: Optional[bool] = Query(None, description="Filter by driver availability"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedDriversResponse:
    """
    Lists commercial drivers with masked license numbers and license validity indicators.
    """
    return await TransporterService.list_drivers(
        session=db,
        organization_id=current_user.organization_id,
        transporter_id=transporter_id,
        page=page,
        page_size=page_size,
        search=search,
        is_available=is_available,
    )


@router.put("/{driver_id}", response_model=DriverListItem)
async def update_driver(
    driver_id: uuid.UUID,
    data: DriverUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DriverListItem:
    """
    Updates driver contact information, license dates, and assigned vehicle.
    """
    return await TransporterService.update_driver(
        session=db,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        driver_id=driver_id,
        data=data,
    )


@router.post("/{driver_id}/assign-vehicle", response_model=DriverListItem)
async def assign_driver_to_vehicle(
    driver_id: uuid.UUID,
    data: DriverAssignmentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DriverListItem:
    """
    Assigns or unassigns a driver to a fleet vehicle.
    Blocks assignment if the driver's commercial license has expired.
    """
    return await TransporterService.assign_driver_to_vehicle(
        session=db,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        driver_id=driver_id,
        data=data,
    )


@router.delete("/{driver_id}")
async def delete_driver(
    driver_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Soft deletes a driver.
    """
    return await TransporterService.delete_driver(
        session=db,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        driver_id=driver_id,
    )
