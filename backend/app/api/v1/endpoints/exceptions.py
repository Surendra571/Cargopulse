import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.auth import User
from app.models.enums import ExceptionPriority, ExceptionSeverity, ExceptionStatus, ExceptionType
from app.schemas.exception import (
    ExceptionAcknowledgeRequest,
    ExceptionAssignRequest,
    ExceptionCloseRequest,
    ExceptionCreateRequest,
    ExceptionDetailResponse,
    ExceptionEscalateRequest,
    ExceptionListResponse,
    ExceptionMetricsResponse,
    ExceptionResolveRequest,
    ExceptionResponse,
    ExceptionUpdateRequest,
)
from app.services.exception_service import ExceptionService

router = APIRouter(prefix="/exceptions", tags=["Exception Management"])


@router.get("", response_model=ExceptionListResponse)
async def list_exceptions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[ExceptionStatus] = Query(None),
    severity: Optional[ExceptionSeverity] = Query(None),
    priority: Optional[ExceptionPriority] = Query(None),
    exception_type: Optional[ExceptionType] = Query(None),
    shipment_id: Optional[uuid.UUID] = Query(None),
    transporter_id: Optional[uuid.UUID] = Query(None),
    assigned_owner_id: Optional[uuid.UUID] = Query(None),
    search: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Lists operational exceptions with filtering and search."""
    return await ExceptionService.list_exceptions(
        session=session,
        organization_id=current_user.organization_id,
        page=page,
        page_size=page_size,
        status_filter=status,
        severity_filter=severity,
        priority_filter=priority,
        exception_type=exception_type,
        shipment_id=shipment_id,
        transporter_id=transporter_id,
        assigned_owner_id=assigned_owner_id,
        search=search,
    )


@router.get("/metrics", response_model=ExceptionMetricsResponse)
async def get_exception_metrics(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Aggregates exception metrics, severity breakdown, and SLA resolution times."""
    return await ExceptionService.get_metrics(
        session=session,
        organization_id=current_user.organization_id,
    )


@router.get("/{exception_id}", response_model=ExceptionDetailResponse)
async def get_exception_detail(
    exception_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Fetches full exception detail including audit history and linked recovery cases."""
    return await ExceptionService.get_exception_detail(
        session=session,
        organization_id=current_user.organization_id,
        exception_id=exception_id,
    )


@router.post("", response_model=ExceptionResponse, status_code=status.HTTP_201_CREATED)
async def create_exception(
    payload: ExceptionCreateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Manual or automated exception logging with duplicate detection."""
    return await ExceptionService.create_exception(
        session=session,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        data=payload,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@router.post("/{exception_id}/acknowledge", response_model=ExceptionResponse)
async def acknowledge_exception(
    exception_id: uuid.UUID,
    payload: ExceptionAcknowledgeRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Transitions exception from OPEN to ACKNOWLEDGED."""
    return await ExceptionService.acknowledge_exception(
        session=session,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        exception_id=exception_id,
        data=payload,
    )


@router.post("/{exception_id}/assign", response_model=ExceptionResponse)
async def assign_exception(
    exception_id: uuid.UUID,
    payload: ExceptionAssignRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Assigns or reassigns an exception to an owner."""
    return await ExceptionService.assign_exception(
        session=session,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        exception_id=exception_id,
        data=payload,
    )


@router.post("/{exception_id}/escalate", response_model=ExceptionResponse)
async def escalate_exception(
    exception_id: uuid.UUID,
    payload: ExceptionEscalateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Escalates an exception to CRITICAL severity and alerts control tower."""
    return await ExceptionService.escalate_exception(
        session=session,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        exception_id=exception_id,
        data=payload,
    )


@router.post("/{exception_id}/resolve", response_model=ExceptionResponse)
async def resolve_exception(
    exception_id: uuid.UUID,
    payload: ExceptionResolveRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Records root cause analysis and resolves the incident."""
    return await ExceptionService.resolve_exception(
        session=session,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        exception_id=exception_id,
        data=payload,
    )


@router.post("/{exception_id}/close", response_model=ExceptionResponse)
async def close_exception(
    exception_id: uuid.UUID,
    payload: ExceptionCloseRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Final closure of the exception incident."""
    return await ExceptionService.close_exception(
        session=session,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        exception_id=exception_id,
        data=payload,
    )
