import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import (
    ExceptionPriority,
    ExceptionSeverity,
    ExceptionStatus,
    ExceptionType,
    NotificationChannel,
    NotificationStatus,
)
from app.models.integrations import AuditLog, Notification
from app.models.operations import ExceptionRecord, RecoveryCase
from app.models.shipment import Shipment, ShipmentEvent
from app.models.transporter import Transporter
from app.models.auth import User
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
    ExceptionShipmentSummary,
    ExceptionTransporterSummary,
    ExceptionUpdateRequest,
    ExceptionUserSummary,
)


class ExceptionService:
    @classmethod
    async def _format_exception_response(cls, exc: ExceptionRecord) -> ExceptionResponse:
        shipment_summary = None
        if hasattr(exc, "__dict__") and "shipment" in exc.__dict__ and exc.shipment:
            s = exc.shipment
            shipment_summary = ExceptionShipmentSummary(
                id=str(s.id),
                tracking_number=s.tracking_number,
                status=s.status.value if hasattr(s.status, "value") else str(s.status),
                origin_city=s.origin_city,
                destination_city=s.destination_city,
            )

        transporter_summary = None
        if hasattr(exc, "__dict__") and "transporter" in exc.__dict__ and exc.transporter:
            t = exc.transporter
            transporter_summary = ExceptionTransporterSummary(
                id=str(t.id),
                name=t.name,
                code=t.code,
            )

        owner_summary = None
        if hasattr(exc, "__dict__") and "assigned_owner" in exc.__dict__ and exc.assigned_owner:
            u = exc.assigned_owner
            owner_summary = ExceptionUserSummary(
                id=str(u.id),
                full_name=u.full_name,
                email=u.email,
            )

        return ExceptionResponse(
            id=str(exc.id),
            organization_id=str(exc.organization_id),
            shipment_id=str(exc.shipment_id) if exc.shipment_id else None,
            transporter_id=str(exc.transporter_id) if exc.transporter_id else None,
            exception_type=exc.exception_type,
            severity=exc.severity,
            priority=exc.priority,
            status=exc.status,
            title=exc.title,
            description=exc.description,
            root_cause=exc.root_cause,
            escalation_level=exc.escalation_level,
            escalated_at=exc.escalated_at,
            reported_at=exc.reported_at,
            acknowledged_at=exc.acknowledged_at,
            acknowledged_by_user_id=str(exc.acknowledged_by_user_id) if exc.acknowledged_by_user_id else None,
            resolved_at=exc.resolved_at,
            resolution_notes=exc.resolution_notes,
            closed_at=exc.closed_at,
            closed_by_user_id=str(exc.closed_by_user_id) if exc.closed_by_user_id else None,
            closure_reason=exc.closure_reason,
            reported_by_user_id=str(exc.reported_by_user_id) if exc.reported_by_user_id else None,
            assigned_owner_id=str(exc.assigned_owner_id) if exc.assigned_owner_id else None,
            context_data=dict(exc.context_data or {}),
            created_at=exc.created_at,
            updated_at=exc.updated_at,
            shipment=shipment_summary,
            transporter=transporter_summary,
            assigned_owner=owner_summary,
        )

    @classmethod
    async def list_exceptions(
        cls,
        session: AsyncSession,
        organization_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
        status_filter: Optional[ExceptionStatus] = None,
        severity_filter: Optional[ExceptionSeverity] = None,
        priority_filter: Optional[ExceptionPriority] = None,
        exception_type: Optional[ExceptionType] = None,
        shipment_id: Optional[uuid.UUID] = None,
        transporter_id: Optional[uuid.UUID] = None,
        assigned_owner_id: Optional[uuid.UUID] = None,
        search: Optional[str] = None,
    ) -> ExceptionListResponse:
        query = (
            select(ExceptionRecord)
            .where(
                ExceptionRecord.organization_id == organization_id,
                ExceptionRecord.is_deleted == False,
            )
            .options(
                selectinload(ExceptionRecord.shipment),
                selectinload(ExceptionRecord.transporter),
                selectinload(ExceptionRecord.assigned_owner),
            )
        )

        if status_filter:
            query = query.where(ExceptionRecord.status == status_filter)
        if severity_filter:
            query = query.where(ExceptionRecord.severity == severity_filter)
        if priority_filter:
            query = query.where(ExceptionRecord.priority == priority_filter.value)
        if exception_type:
            query = query.where(ExceptionRecord.exception_type == exception_type)
        if shipment_id:
            query = query.where(ExceptionRecord.shipment_id == shipment_id)
        if transporter_id:
            query = query.where(ExceptionRecord.transporter_id == transporter_id)
        if assigned_owner_id:
            query = query.where(ExceptionRecord.assigned_owner_id == assigned_owner_id)

        if search and search.strip():
            term = f"%{search.strip()}%"
            query = query.where(
                or_(
                    ExceptionRecord.title.ilike(term),
                    ExceptionRecord.description.ilike(term),
                )
            )

        count_stmt = select(func.count()).select_from(query.subquery())
        total = (await session.execute(count_stmt)).scalar() or 0

        offset = (page - 1) * page_size
        query = query.order_by(desc(ExceptionRecord.reported_at)).offset(offset).limit(page_size)
        items = list((await session.execute(query)).scalars().all())

        formatted = [await cls._format_exception_response(e) for e in items]
        pages = (total + page_size - 1) // page_size if page_size > 0 else 1

        return ExceptionListResponse(items=formatted, total=total, page=page, page_size=page_size, pages=pages)

    @classmethod
    async def get_exception_detail(
        cls,
        session: AsyncSession,
        organization_id: uuid.UUID,
        exception_id: uuid.UUID,
    ) -> ExceptionDetailResponse:
        stmt = (
            select(ExceptionRecord)
            .where(
                ExceptionRecord.id == exception_id,
                ExceptionRecord.organization_id == organization_id,
                ExceptionRecord.is_deleted == False,
            )
            .options(
                selectinload(ExceptionRecord.shipment),
                selectinload(ExceptionRecord.transporter),
                selectinload(ExceptionRecord.assigned_owner),
                selectinload(ExceptionRecord.recovery_cases),
            )
        )
        exc = (await session.execute(stmt)).scalar_one_or_none()
        if not exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exception incident not found.")

        base_res = await cls._format_exception_response(exc)

        # Recovery cases
        cases = []
        for rc in exc.recovery_cases:
            cases.append({
                "id": str(rc.id),
                "case_number": rc.case_number,
                "strategy": rc.strategy.value if hasattr(rc.strategy, "value") else str(rc.strategy),
                "status": rc.status.value if hasattr(rc.status, "value") else str(rc.status),
                "approval_status": rc.approval_status,
                "proposed_solution": rc.proposed_solution,
                "created_at": rc.created_at.isoformat(),
            })

        # Audit trail
        audit_stmt = (
            select(AuditLog)
            .where(
                AuditLog.organization_id == organization_id,
                AuditLog.entity_name == "ExceptionRecord",
                AuditLog.entity_id == exc.id,
            )
            .order_by(desc(AuditLog.created_at))
            .limit(20)
        )
        audits = list((await session.execute(audit_stmt)).scalars().all())
        audit_list = [
            {
                "id": str(a.id),
                "action": a.action,
                "user_id": str(a.user_id) if a.user_id else None,
                "changes": a.changes,
                "created_at": a.created_at.isoformat(),
            }
            for a in audits
        ]

        return ExceptionDetailResponse(
            **base_res.model_dump(),
            recovery_cases=cases,
            audit_trail=audit_list,
        )

    @classmethod
    async def create_exception(
        cls,
        session: AsyncSession,
        organization_id: uuid.UUID,
        user_id: Optional[uuid.UUID],
        data: ExceptionCreateRequest,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> ExceptionResponse:
        """
        Creates an operational exception record with duplicate detection.
        If an open exception already exists for this shipment and type, merges context and avoids duplicates.
        """
        now = datetime.now(timezone.utc)

        # 1. Duplicate Detection Check
        if data.shipment_id:
            dup_stmt = select(ExceptionRecord).where(
                ExceptionRecord.organization_id == organization_id,
                ExceptionRecord.shipment_id == data.shipment_id,
                ExceptionRecord.exception_type == data.exception_type,
                ExceptionRecord.status.in_([
                    ExceptionStatus.OPEN,
                    ExceptionStatus.ACKNOWLEDGED,
                    ExceptionStatus.INVESTIGATING,
                    ExceptionStatus.RESOLVING,
                    ExceptionStatus.RECOVERY_IN_PROGRESS,
                ]),
                ExceptionRecord.is_deleted == False,
            ).options(
                selectinload(ExceptionRecord.shipment),
                selectinload(ExceptionRecord.transporter),
                selectinload(ExceptionRecord.assigned_owner),
            )
            existing = (await session.execute(dup_stmt)).scalar_one_or_none()
            if existing:
                # Merge context data and bump timestamp without duplicating record
                ctx = dict(existing.context_data or {})
                ctx["duplicate_reported_at"] = now.isoformat()
                if data.context_data:
                    ctx.update(data.context_data)
                existing.context_data = ctx
                existing.updated_at = now
                await session.commit()
                return await cls._format_exception_response(existing)

        # 2. Create new exception record
        new_exc = ExceptionRecord(
            id=uuid.uuid4(),
            organization_id=organization_id,
            shipment_id=data.shipment_id,
            transporter_id=data.transporter_id,
            exception_type=data.exception_type,
            severity=data.severity,
            priority=data.priority.value,
            status=ExceptionStatus.OPEN,
            title=data.title,
            description=data.description,
            reported_at=now,
            reported_by_user_id=user_id,
            assigned_owner_id=data.assigned_owner_id,
            context_data=data.context_data or {},
        )
        session.add(new_exc)

        # 3. Shipment Event
        if data.shipment_id:
            event = ShipmentEvent(
                organization_id=organization_id,
                shipment_id=data.shipment_id,
                event_type=f"EXCEPTION_{data.exception_type.value}",
                description=f"Operational exception logged: {data.title} ({data.severity.value}).",
                occurred_at=now,
                source="EXCEPTION_CONTROL_TOWER",
                created_by_user_id=user_id,
                payload={
                    "exception_id": str(new_exc.id),
                    "exception_type": data.exception_type.value,
                    "severity": data.severity.value,
                },
            )
            session.add(event)

        # 4. Audit Log
        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="CREATE_EXCEPTION",
            entity_name="ExceptionRecord",
            entity_id=new_exc.id,
            ip_address=ip_address,
            user_agent=user_agent,
            changes={
                "exception_type": data.exception_type.value,
                "severity": data.severity.value,
                "priority": data.priority.value,
                "title": data.title,
            },
        )
        session.add(audit)

        # 5. Notification
        notif = Notification(
            organization_id=organization_id,
            recipient_user_id=data.assigned_owner_id,
            channel=NotificationChannel.IN_APP,
            status=NotificationStatus.QUEUED,
            destination="OPERATIONS_TOWER",
            title=f"Exception Alert: {data.title}",
            body=f"{data.severity.value} priority exception reported: {data.description[:120]}...",
            metadata_payload={"type": "NEW_EXCEPTION", "exception_id": str(new_exc.id)},
        )
        session.add(notif)

        await session.commit()
        return await cls.get_exception_detail(session, organization_id, new_exc.id)

    @classmethod
    async def acknowledge_exception(
        cls,
        session: AsyncSession,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        exception_id: uuid.UUID,
        data: ExceptionAcknowledgeRequest,
    ) -> ExceptionResponse:
        """Transitions exception state from OPEN to ACKNOWLEDGED."""
        now = datetime.now(timezone.utc)
        stmt = (
            select(ExceptionRecord)
            .where(
                ExceptionRecord.id == exception_id,
                ExceptionRecord.organization_id == organization_id,
                ExceptionRecord.is_deleted == False,
            )
            .options(
                selectinload(ExceptionRecord.shipment),
                selectinload(ExceptionRecord.transporter),
                selectinload(ExceptionRecord.assigned_owner),
            )
            .with_for_update()
        )
        exc = (await session.execute(stmt)).scalar_one_or_none()
        if not exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exception not found.")

        if exc.status != ExceptionStatus.OPEN:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot acknowledge exception in status '{exc.status.value}'. Must be OPEN.",
            )

        exc.status = ExceptionStatus.ACKNOWLEDGED
        exc.acknowledged_at = now
        exc.acknowledged_by_user_id = user_id
        if not exc.assigned_owner_id:
            exc.assigned_owner_id = user_id

        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="ACKNOWLEDGE_EXCEPTION",
            entity_name="ExceptionRecord",
            entity_id=exc.id,
            changes={"status": ExceptionStatus.ACKNOWLEDGED.value, "notes": data.notes},
        )
        session.add(audit)

        res = await cls._format_exception_response(exc)
        await session.commit()
        return res

    @classmethod
    async def assign_exception(
        cls,
        session: AsyncSession,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        exception_id: uuid.UUID,
        data: ExceptionAssignRequest,
    ) -> ExceptionResponse:
        """Assigns or reassigns an exception to an operations coordinator."""
        stmt = (
            select(ExceptionRecord)
            .where(
                ExceptionRecord.id == exception_id,
                ExceptionRecord.organization_id == organization_id,
                ExceptionRecord.is_deleted == False,
            )
            .options(
                selectinload(ExceptionRecord.shipment),
                selectinload(ExceptionRecord.transporter),
                selectinload(ExceptionRecord.assigned_owner),
            )
            .with_for_update()
        )
        exc = (await session.execute(stmt)).scalar_one_or_none()
        if not exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exception not found.")

        # Verify assignee belongs to organization
        u_stmt = select(User).where(User.id == data.assigned_owner_id, User.organization_id == organization_id)
        assignee = (await session.execute(u_stmt)).scalar_one_or_none()
        if not assignee:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignee user not found in your organization.")

        prev_owner = exc.assigned_owner_id
        exc.assigned_owner_id = assignee.id
        if exc.status in [ExceptionStatus.OPEN, ExceptionStatus.ACKNOWLEDGED]:
            exc.status = ExceptionStatus.INVESTIGATING

        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="ASSIGN_EXCEPTION",
            entity_name="ExceptionRecord",
            entity_id=exc.id,
            changes={
                "previous_owner_id": str(prev_owner) if prev_owner else None,
                "assigned_owner_id": str(assignee.id),
                "assigned_owner_name": assignee.full_name,
                "status": exc.status.value,
            },
        )
        session.add(audit)

        exc.assigned_owner = assignee
        res = await cls._format_exception_response(exc)
        await session.commit()
        return res

    @classmethod
    async def escalate_exception(
        cls,
        session: AsyncSession,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        exception_id: uuid.UUID,
        data: ExceptionEscalateRequest,
    ) -> ExceptionResponse:
        """Escalates an exception, bumps severity/priority, and alerts leadership."""
        now = datetime.now(timezone.utc)
        stmt = (
            select(ExceptionRecord)
            .where(
                ExceptionRecord.id == exception_id,
                ExceptionRecord.organization_id == organization_id,
                ExceptionRecord.is_deleted == False,
            )
            .options(
                selectinload(ExceptionRecord.shipment),
                selectinload(ExceptionRecord.transporter),
                selectinload(ExceptionRecord.assigned_owner),
            )
            .with_for_update()
        )
        exc = (await session.execute(stmt)).scalar_one_or_none()
        if not exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exception not found.")

        exc.escalation_level += 1
        exc.escalated_at = now
        exc.severity = data.target_severity or ExceptionSeverity.CRITICAL
        exc.priority = "CRITICAL"

        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="ESCALATE_EXCEPTION",
            entity_name="ExceptionRecord",
            entity_id=exc.id,
            changes={
                "escalation_level": exc.escalation_level,
                "escalation_reason": data.escalation_reason,
                "severity": exc.severity.value,
            },
        )
        session.add(audit)

        notif = Notification(
            organization_id=organization_id,
            recipient_user_id=None,
            channel=NotificationChannel.IN_APP,
            status=NotificationStatus.QUEUED,
            destination="LEADERSHIP_DESK",
            title=f"ESCALATION ALERT (L{exc.escalation_level}): {exc.title}",
            body=f"Exception escalated to {exc.severity.value}. Reason: {data.escalation_reason}",
            metadata_payload={"type": "EXCEPTION_ESCALATED", "exception_id": str(exc.id)},
        )
        session.add(notif)

        res = await cls._format_exception_response(exc)
        await session.commit()
        return res

    @classmethod
    async def resolve_exception(
        cls,
        session: AsyncSession,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        exception_id: uuid.UUID,
        data: ExceptionResolveRequest,
    ) -> ExceptionResponse:
        """Resolves an exception with root cause diagnosis and resolution notes."""
        now = datetime.now(timezone.utc)
        stmt = (
            select(ExceptionRecord)
            .where(
                ExceptionRecord.id == exception_id,
                ExceptionRecord.organization_id == organization_id,
                ExceptionRecord.is_deleted == False,
            )
            .options(
                selectinload(ExceptionRecord.shipment),
                selectinload(ExceptionRecord.transporter),
                selectinload(ExceptionRecord.assigned_owner),
            )
            .with_for_update()
        )
        exc = (await session.execute(stmt)).scalar_one_or_none()
        if not exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exception not found.")

        if exc.status in [ExceptionStatus.RESOLVED, ExceptionStatus.CLOSED]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Exception is already resolved or closed.")

        exc.status = ExceptionStatus.RESOLVED
        exc.resolved_at = now
        exc.root_cause = data.root_cause
        exc.resolution_notes = data.resolution_notes

        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="RESOLVE_EXCEPTION",
            entity_name="ExceptionRecord",
            entity_id=exc.id,
            changes={
                "status": ExceptionStatus.RESOLVED.value,
                "root_cause": data.root_cause,
                "resolution_notes": data.resolution_notes,
            },
        )
        session.add(audit)

        res = await cls._format_exception_response(exc)
        await session.commit()
        return res

    @classmethod
    async def close_exception(
        cls,
        session: AsyncSession,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        exception_id: uuid.UUID,
        data: ExceptionCloseRequest,
    ) -> ExceptionResponse:
        """Final closure of exception record after verification."""
        now = datetime.now(timezone.utc)
        stmt = (
            select(ExceptionRecord)
            .where(
                ExceptionRecord.id == exception_id,
                ExceptionRecord.organization_id == organization_id,
                ExceptionRecord.is_deleted == False,
            )
            .options(
                selectinload(ExceptionRecord.shipment),
                selectinload(ExceptionRecord.transporter),
                selectinload(ExceptionRecord.assigned_owner),
            )
            .with_for_update()
        )
        exc = (await session.execute(stmt)).scalar_one_or_none()
        if not exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exception not found.")

        exc.status = ExceptionStatus.CLOSED
        exc.closed_at = now
        exc.closed_by_user_id = user_id
        exc.closure_reason = data.closure_reason

        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="CLOSE_EXCEPTION",
            entity_name="ExceptionRecord",
            entity_id=exc.id,
            changes={
                "status": ExceptionStatus.CLOSED.value,
                "closure_reason": data.closure_reason,
            },
        )
        session.add(audit)

        res = await cls._format_exception_response(exc)
        await session.commit()
        return res

    @classmethod
    async def get_metrics(
        cls,
        session: AsyncSession,
        organization_id: uuid.UUID,
    ) -> ExceptionMetricsResponse:
        """Aggregates operational exception telemetry and SLA resolution metrics."""
        base_stmt = select(ExceptionRecord).where(
            ExceptionRecord.organization_id == organization_id,
            ExceptionRecord.is_deleted == False,
        )

        all_exceptions = list((await session.execute(base_stmt)).scalars().all())
        total = len(all_exceptions)

        open_cnt = sum(1 for e in all_exceptions if e.status == ExceptionStatus.OPEN)
        investigating_cnt = sum(1 for e in all_exceptions if e.status in [ExceptionStatus.ACKNOWLEDGED, ExceptionStatus.INVESTIGATING, ExceptionStatus.RESOLVING, ExceptionStatus.RECOVERY_IN_PROGRESS])
        resolved_cnt = sum(1 for e in all_exceptions if e.status == ExceptionStatus.RESOLVED)
        closed_cnt = sum(1 for e in all_exceptions if e.status == ExceptionStatus.CLOSED)

        crit_cnt = sum(1 for e in all_exceptions if e.severity == ExceptionSeverity.CRITICAL or e.priority == "CRITICAL")
        high_cnt = sum(1 for e in all_exceptions if (e.severity == ExceptionSeverity.HIGH or e.priority == "HIGH") and e.severity != ExceptionSeverity.CRITICAL)
        med_cnt = sum(1 for e in all_exceptions if e.severity == ExceptionSeverity.MEDIUM and e.priority != "CRITICAL" and e.priority != "HIGH")
        low_cnt = sum(1 for e in all_exceptions if e.severity == ExceptionSeverity.LOW)

        by_type: Dict[str, int] = {}
        resolution_hours: List[float] = []

        for e in all_exceptions:
            t = e.exception_type.value if hasattr(e.exception_type, "value") else str(e.exception_type)
            by_type[t] = by_type.get(t, 0) + 1

            if e.resolved_at and e.reported_at:
                diff = (e.resolved_at - e.reported_at).total_seconds() / 3600.0
                if diff >= 0:
                    resolution_hours.append(diff)

        mean_hours = sum(resolution_hours) / len(resolution_hours) if resolution_hours else 0.0

        return ExceptionMetricsResponse(
            total_exceptions=total,
            open_exceptions=open_cnt,
            investigating_exceptions=investigating_cnt,
            resolved_exceptions=resolved_cnt,
            closed_exceptions=closed_cnt,
            critical_count=crit_cnt,
            high_count=high_cnt,
            medium_count=med_cnt,
            low_count=low_cnt,
            by_type=by_type,
            mean_resolution_hours=round(mean_hours, 2),
        )


exception_service = ExceptionService

