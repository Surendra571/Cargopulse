import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.auth import User
from app.schemas.analytics import (
    AnalyticsDashboardResponse,
    LogisticsAnalyticsOverview,
    RouteReliabilityMetric,
    TransporterPerformanceMetric,
)
from app.services.analytics_service import AnalyticsService


router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview", response_model=LogisticsAnalyticsOverview)
async def get_logistics_analytics_overview(
    start_date: Optional[datetime] = Query(None, description="Start date filter (UTC)"),
    end_date: Optional[datetime] = Query(None, description="End date filter (UTC)"),
    transporter_id: Optional[uuid.UUID] = Query(None, description="Optional transporter filter"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LogisticsAnalyticsOverview:
    """
    Returns the 13 core operational logistics analytics metrics for the current tenant.
    """
    return await AnalyticsService.get_overview_metrics(
        session=db,
        organization_id=current_user.organization_id,
        start_date=start_date,
        end_date=end_date,
        transporter_id=transporter_id,
    )


@router.get("/transporters", response_model=List[TransporterPerformanceMetric])
async def get_transporter_analytics(
    start_date: Optional[datetime] = Query(None, description="Start date filter (UTC)"),
    end_date: Optional[datetime] = Query(None, description="End date filter (UTC)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[TransporterPerformanceMetric]:
    """
    Returns performance rankings, reliability scores, and trends for all transporters.
    """
    return await AnalyticsService.get_transporter_metrics(
        session=db,
        organization_id=current_user.organization_id,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/transporters/{transporter_id}", response_model=TransporterPerformanceMetric)
async def get_single_transporter_analytics(
    transporter_id: uuid.UUID,
    start_date: Optional[datetime] = Query(None, description="Start date filter (UTC)"),
    end_date: Optional[datetime] = Query(None, description="End date filter (UTC)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TransporterPerformanceMetric:
    """
    Returns granular performance metrics, routes, and historical trend for a single transporter.
    """
    metrics = await AnalyticsService.get_transporter_metrics(
        session=db,
        organization_id=current_user.organization_id,
        transporter_id=transporter_id,
        start_date=start_date,
        end_date=end_date,
    )
    if not metrics:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transporter analytics not found or no access",
        )
    return metrics[0]


@router.get("/routes", response_model=List[RouteReliabilityMetric])
async def get_route_reliability_analytics(
    start_date: Optional[datetime] = Query(None, description="Start date filter (UTC)"),
    end_date: Optional[datetime] = Query(None, description="End date filter (UTC)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[RouteReliabilityMetric]:
    """
    Returns lane-by-lane reliability metrics, transit times, and delay statistics.
    """
    return await AnalyticsService.get_route_reliability_metrics(
        session=db,
        organization_id=current_user.organization_id,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/dashboard", response_model=AnalyticsDashboardResponse)
async def get_analytics_dashboard_bundle(
    start_date: Optional[datetime] = Query(None, description="Start date filter (UTC)"),
    end_date: Optional[datetime] = Query(None, description="End date filter (UTC)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AnalyticsDashboardResponse:
    """
    Returns complete aggregated analytics bundle for the frontend dashboard.
    """
    overview = await AnalyticsService.get_overview_metrics(
        session=db,
        organization_id=current_user.organization_id,
        start_date=start_date,
        end_date=end_date,
    )
    transporters = await AnalyticsService.get_transporter_metrics(
        session=db,
        organization_id=current_user.organization_id,
        start_date=start_date,
        end_date=end_date,
    )
    routes = await AnalyticsService.get_route_reliability_metrics(
        session=db,
        organization_id=current_user.organization_id,
        start_date=start_date,
        end_date=end_date,
    )

    return AnalyticsDashboardResponse(
        timeframe={
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
        },
        overview=overview,
        transporters=transporters,
        routes=routes,
        generated_at=datetime.now(timezone.utc),
    )


@router.get("/export")
async def export_analytics_csv(
    start_date: Optional[datetime] = Query(None, description="Start date filter (UTC)"),
    end_date: Optional[datetime] = Query(None, description="End date filter (UTC)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """
    Streams CSV document containing complete analytics metrics.
    """
    csv_content = await AnalyticsService.export_analytics_csv(
        session=db,
        organization_id=current_user.organization_id,
        start_date=start_date,
        end_date=end_date,
    )
    filename = f"cargopulse_analytics_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
