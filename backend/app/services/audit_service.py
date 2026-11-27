import csv
import io
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import User
from app.models.integrations import AuditLog
from app.schemas.audit import AuditLogResponse


SENSITIVE_KEY_PATTERNS = [
    re.compile(r"pass(word)?", re.IGNORECASE),
    re.compile(r"secret", re.IGNORECASE),
    re.compile(r"token", re.IGNORECASE),
    re.compile(r"api[_-]?key", re.IGNORECASE),
    re.compile(r"auth(orization)?", re.IGNORECASE),
    re.compile(r"hash(ed)?", re.IGNORECASE),
    re.compile(r"card", re.IGNORECASE),
    re.compile(r"cvv", re.IGNORECASE),
    re.compile(r"credential", re.IGNORECASE),
]


def sanitize_audit_data(data: Any) -> Any:
    """
    Recursively strips or masks sensitive credentials and secrets from audit payloads.
    """
    if isinstance(data, dict):
        sanitized = {}
        for key, value in data.items():
            if any(pattern.search(key) for pattern in SENSITIVE_KEY_PATTERNS):
                sanitized[key] = "[REDACTED]"
            else:
                sanitized[key] = sanitize_audit_data(value)
        return sanitized
    elif isinstance(data, list):
        return [sanitize_audit_data(item) for item in data]
    return data


class AuditService:
    """
    Service for writing, querying, and exporting immutable audit trail records.
    Audit records cannot be updated or deleted by normal users or API consumers.
    """

    @classmethod
    async def log_event(
        cls,
        session: AsyncSession,
        *,
        organization_id: uuid.UUID,
        action: str,
        resource_type: str,
        resource_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
        actor_email: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        correlation_id: Optional[str] = None,
        before: Optional[Dict[str, Any]] = None,
        after: Optional[Dict[str, Any]] = None,
        changes: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        commit: bool = False,
    ) -> AuditLog:
        """
        Records an immutable audit trail entry with secret sanitization and tenant scoping.
        """
        # Resolve actor email if user_id is provided and actor_email was not explicitly passed
        if user_id and not actor_email:
            user_res = await session.execute(select(User.email).where(User.id == user_id))
            actor_email = user_res.scalar_one_or_none()

        cid = correlation_id or str(uuid.uuid4())

        sanitized_changes = {
            "correlation_id": cid,
            "actor_email": actor_email,
        }
        if before is not None:
            sanitized_changes["before"] = sanitize_audit_data(before)
        if after is not None:
            sanitized_changes["after"] = sanitize_audit_data(after)
        elif changes is not None:
            sanitized_changes["after"] = sanitize_audit_data(changes)
        if metadata:
            sanitized_changes["metadata"] = sanitize_audit_data(metadata)

        audit_entry = AuditLog(
            id=uuid.uuid4(),
            organization_id=organization_id,
            user_id=user_id,
            actor_email=actor_email,
            action=action.upper(),
            entity_name=resource_type,
            entity_id=resource_id,
            resource_type=resource_type,
            resource_id=resource_id,
            correlation_id=cid,
            ip_address=ip_address,
            user_agent=user_agent,
            changes=sanitized_changes,
            created_at=datetime.now(timezone.utc),
        )

        session.add(audit_entry)
        if commit:
            await session.commit()
            await session.refresh(audit_entry)

        return audit_entry

    @classmethod
    async def query_logs(
        cls,
        session: AsyncSession,
        *,
        organization_id: uuid.UUID,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[uuid.UUID] = None,
        user_id: Optional[uuid.UUID] = None,
        actor_email: Optional[str] = None,
        correlation_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[AuditLogResponse], int]:
        """
        Returns tenant-scoped, paginated audit logs filtered by operational attributes.
        """
        filters = [AuditLog.organization_id == organization_id]

        if action:
            filters.append(AuditLog.action == action.upper())
        if resource_type:
            filters.append(
                func.lower(func.coalesce(AuditLog.resource_type, AuditLog.entity_name))
                == resource_type.lower()
            )
        if resource_id:
            filters.append(
                func.coalesce(AuditLog.resource_id, AuditLog.entity_id) == resource_id
            )
        if user_id:
            filters.append(AuditLog.user_id == user_id)
        if actor_email:
            filters.append(func.lower(AuditLog.actor_email) == actor_email.lower())
        if correlation_id:
            filters.append(AuditLog.correlation_id == correlation_id)
        if start_date:
            filters.append(AuditLog.created_at >= start_date)
        if end_date:
            filters.append(AuditLog.created_at <= end_date)
        if search:
            search_pattern = f"%{search.lower()}%"
            filters.append(
                (func.lower(AuditLog.action).like(search_pattern))
                | (func.lower(func.coalesce(AuditLog.actor_email, "")).like(search_pattern))
                | (func.lower(func.coalesce(AuditLog.resource_type, AuditLog.entity_name)).like(search_pattern))
                | (func.lower(func.coalesce(AuditLog.correlation_id, "")).like(search_pattern))
            )

        # Count total
        count_stmt = select(func.count(AuditLog.id)).where(and_(*filters))
        total = (await session.execute(count_stmt)).scalar() or 0

        # Query page
        offset = (page - 1) * page_size
        stmt = (
            select(AuditLog)
            .where(and_(*filters))
            .order_by(desc(AuditLog.created_at))
            .offset(offset)
            .limit(page_size)
        )
        result = await session.execute(stmt)
        records = result.scalars().all()

        responses = []
        for r in records:
            res_type = r.resource_type or r.entity_name
            res_id = r.resource_id or r.entity_id
            email = r.actor_email
            cid = r.correlation_id
            if not cid and r.changes and isinstance(r.changes, dict):
                cid = r.changes.get("correlation_id")
            if not email and r.changes and isinstance(r.changes, dict):
                email = r.changes.get("actor_email")

            responses.append(
                AuditLogResponse(
                    id=r.id,
                    organization_id=r.organization_id,
                    user_id=r.user_id,
                    actor_email=email,
                    action=r.action,
                    resource_type=res_type,
                    resource_id=res_id,
                    correlation_id=cid,
                    ip_address=r.ip_address,
                    user_agent=r.user_agent,
                    changes=r.changes or {},
                    created_at=r.created_at,
                )
            )

        return responses, total

    @classmethod
    async def export_logs_csv(
        cls,
        session: AsyncSession,
        *,
        organization_id: uuid.UUID,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 5000,
    ) -> str:
        """
        Generates CSV content of the tenant's audit trail records.
        """
        filters = [AuditLog.organization_id == organization_id]
        if action:
            filters.append(AuditLog.action == action.upper())
        if resource_type:
            filters.append(
                func.lower(func.coalesce(AuditLog.resource_type, AuditLog.entity_name))
                == resource_type.lower()
            )
        if start_date:
            filters.append(AuditLog.created_at >= start_date)
        if end_date:
            filters.append(AuditLog.created_at <= end_date)

        stmt = (
            select(AuditLog)
            .where(and_(*filters))
            .order_by(desc(AuditLog.created_at))
            .limit(limit)
        )
        records = (await session.execute(stmt)).scalars().all()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Audit ID",
            "Timestamp (UTC)",
            "Action",
            "Resource Type",
            "Resource ID",
            "Actor Email",
            "Actor User ID",
            "IP Address",
            "Correlation ID",
            "Changes / Summary",
        ])

        for r in records:
            res_type = r.resource_type or r.entity_name
            res_id = r.resource_id or r.entity_id
            email = r.actor_email or (r.changes.get("actor_email") if r.changes else "")
            cid = r.correlation_id or (r.changes.get("correlation_id") if r.changes else "")
            summary = str(r.changes) if r.changes else ""

            writer.writerow([
                str(r.id),
                r.created_at.isoformat() if r.created_at else "",
                r.action,
                res_type,
                str(res_id),
                email or "system",
                str(r.user_id) if r.user_id else "",
                r.ip_address or "",
                cid or "",
                summary,
            ])

        return output.getvalue()
