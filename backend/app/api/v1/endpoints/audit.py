import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.auth import User
from app.schemas.audit import (
    AuditLogListResponse,
    AuditLogResponse,
    CreateAuditEventRequest,
)
from app.services.audit_service import AuditService


router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/logs", response_model=AuditLogListResponse)
async def get_audit_logs(
    action: Optional[str] = Query(None, description="Filter by action name, e.g. SHIPMENT_CREATED"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type, e.g. Shipment"),
    resource_id: Optional[uuid.UUID] = Query(None, description="Filter by resource UUID"),
    user_id: Optional[uuid.UUID] = Query(None, description="Filter by actor user UUID"),
    actor_email: Optional[str] = Query(None, description="Filter by actor email"),
    correlation_id: Optional[str] = Query(None, description="Filter by correlation ID"),
    start_date: Optional[datetime] = Query(None, description="Filter by timestamp >= start_date"),
    end_date: Optional[datetime] = Query(None, description="Filter by timestamp <= end_date"),
    search: Optional[str] = Query(None, description="Search term matching action, resource, email, or correlation ID"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Page size"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AuditLogListResponse:
    """
    Returns tenant-scoped, paginated audit logs for compliance, security, and traceability.
    """
    items, total = await AuditService.query_logs(
        session=db,
        organization_id=current_user.organization_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        user_id=user_id,
        actor_email=actor_email,
        correlation_id=correlation_id,
        start_date=start_date,
        end_date=end_date,
        search=search,
        page=page,
        page_size=page_size,
    )
    total_pages = (total + page_size - 1) // page_size if total > 0 else 1

    return AuditLogListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/export")
async def export_audit_logs_csv(
    action: Optional[str] = Query(None),
    resource_type: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """
    Streams CSV document containing tenant audit trail records.
    """
    csv_content = await AuditService.export_logs_csv(
        session=db,
        organization_id=current_user.organization_id,
        action=action,
        resource_type=resource_type,
        start_date=start_date,
        end_date=end_date,
    )
    filename = f"cargopulse_audit_trail_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/events", response_model=AuditLogResponse, status_code=status.HTTP_201_CREATED)
async def create_custom_audit_event(
    request: CreateAuditEventRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AuditLogResponse:
    """
    Explicitly logs an audited operational event (e.g. security action, permission change).
    Normal users cannot edit or delete audit records once created.
    """
    entry = await AuditService.log_event(
        session=db,
        organization_id=current_user.organization_id,
        action=request.action,
        resource_type=request.resource_type,
        resource_id=request.resource_id,
        user_id=current_user.id,
        actor_email=current_user.email,
        correlation_id=request.correlation_id,
        before=request.before,
        after=request.after,
        metadata=request.metadata,
        commit=True,
    )

    return AuditLogResponse(
        id=entry.id,
        organization_id=entry.organization_id,
        user_id=entry.user_id,
        actor_email=entry.actor_email,
        action=entry.action,
        resource_type=entry.resource_type or entry.entity_name,
        resource_id=entry.resource_id or entry.entity_id,
        correlation_id=entry.correlation_id,
        ip_address=entry.ip_address,
        user_agent=entry.user_agent,
        changes=entry.changes or {},
        created_at=entry.created_at,
    )


@router.put("/logs/{log_id}")
@router.patch("/logs/{log_id}")
@router.delete("/logs/{log_id}")
async def forbid_audit_modification(
    log_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
):
    """
    Strict compliance rule: Audit logs are immutable and cannot be updated or deleted.
    """
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Audit trail logs are immutable and cannot be modified or deleted.",
    )
