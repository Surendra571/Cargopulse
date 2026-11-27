import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.auth import User
from app.schemas.dashboard import (
    DashboardMetricsResponse,
    DashboardOverviewResponse,
    ExceptionDistributionItem,
    PaginatedExceptionsResponse,
    PaginatedShipmentsResponse,
    ShipmentDetailResponse,
    TransporterReliabilityItem,
    VolumeOverTimePoint,
)
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["Operations Dashboard"])


@router.get("/overview", response_model=DashboardOverviewResponse)
async def get_dashboard_overview(
    start_date: Optional[datetime] = Query(None, description="Start date filter (UTC)"),
    end_date: Optional[datetime] = Query(None, description="End date filter (UTC)"),
    transporter_id: Optional[uuid.UUID] = Query(None, description="Filter by transporter UUID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DashboardOverviewResponse:
    """
    Returns complete aggregated dashboard bundle for the current user's organization.
    """
    return await DashboardService.get_overview(
        session=db,
        organization_id=current_user.organization_id,
        start_date=start_date,
        end_date=end_date,
        transporter_id=transporter_id,
    )


@router.get("/metrics", response_model=DashboardMetricsResponse)
async def get_dashboard_metrics(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    transporter_id: Optional[uuid.UUID] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DashboardMetricsResponse:
    """
    Returns lightweight core KPI metrics for real-time polling.
    """
    return await DashboardService.get_metrics(
        session=db,
        organization_id=current_user.organization_id,
        start_date=start_date,
        end_date=end_date,
        transporter_id=transporter_id,
    )


@router.get("/charts/volume", response_model=List[VolumeOverTimePoint])
async def get_volume_chart(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    transporter_id: Optional[uuid.UUID] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[VolumeOverTimePoint]:
    """
    Returns daily shipment volume, delivered count, and exception count series.
    """
    return await DashboardService.get_volume_over_time(
        session=db,
        organization_id=current_user.organization_id,
        start_date=start_date,
        end_date=end_date,
        transporter_id=transporter_id,
    )


@router.get("/charts/transporters", response_model=List[TransporterReliabilityItem])
async def get_transporter_rankings(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[TransporterReliabilityItem]:
    """
    Returns transporter reliability leaderboard with SLA performance and load counts.
    """
    return await DashboardService.get_transporter_rankings(
        session=db,
        organization_id=current_user.organization_id,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/tables/attention", response_model=PaginatedShipmentsResponse)
async def get_attention_shipments(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None),
    transporter_id: Optional[uuid.UUID] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedShipmentsResponse:
    """
    Shipments requiring immediate operational attention (failed pickups, delayed deliveries, open exceptions).
    """
    return await DashboardService.get_attention_shipments(
        session=db,
        organization_id=current_user.organization_id,
        page=page,
        page_size=page_size,
        search=search,
        transporter_id=transporter_id,
    )


@router.get("/tables/upcoming-pickups", response_model=PaginatedShipmentsResponse)
async def get_upcoming_pickups(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None),
    transporter_id: Optional[uuid.UUID] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedShipmentsResponse:
    """
    Scheduled upcoming pickups awaiting gate arrival and loading.
    """
    return await DashboardService.get_upcoming_pickups(
        session=db,
        organization_id=current_user.organization_id,
        page=page,
        page_size=page_size,
        search=search,
        transporter_id=transporter_id,
    )


@router.get("/tables/failed-pickups", response_model=PaginatedShipmentsResponse)
async def get_failed_pickups(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None),
    transporter_id: Optional[uuid.UUID] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedShipmentsResponse:
    """
    Failed or breached pickups requiring recovery intervention.
    """
    return await DashboardService.get_failed_pickups(
        session=db,
        organization_id=current_user.organization_id,
        page=page,
        page_size=page_size,
        search=search,
        transporter_id=transporter_id,
    )


@router.get("/tables/deliveries", response_model=PaginatedShipmentsResponse)
async def get_recent_deliveries(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None),
    transporter_id: Optional[uuid.UUID] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedShipmentsResponse:
    """
    Recently completed freight deliveries with proof-of-delivery timestamps.
    """
    return await DashboardService.get_recent_deliveries(
        session=db,
        organization_id=current_user.organization_id,
        page=page,
        page_size=page_size,
        search=search,
        transporter_id=transporter_id,
    )


@router.get("/tables/exceptions", response_model=PaginatedExceptionsResponse)
async def get_open_exceptions(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    severity: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedExceptionsResponse:
    """
    Active operational exceptions requiring triage or recovery.
    """
    return await DashboardService.get_open_exceptions(
        session=db,
        organization_id=current_user.organization_id,
        page=page,
        page_size=page_size,
        severity=severity,
        search=search,
    )


@router.get("/shipments/{shipment_id}", response_model=ShipmentDetailResponse)
async def get_shipment_detail(
    shipment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ShipmentDetailResponse:
    """
    Returns full operational details for a specific shipment.
    """
    detail = await DashboardService.get_shipment_detail(
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
