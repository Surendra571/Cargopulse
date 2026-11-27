import re
import secrets
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.integrations import IntegrationConnection
from app.schemas.integrations import (
    IntegrationConnectionCreate,
    IntegrationConnectionResponse,
    IntegrationConnectionUpdate,
)


class IntegrationRegistryService:
    """
    CRUD management for external system integration connections.
    """

    @staticmethod
    def _slugify(text: str) -> str:
        s = re.sub(r"[^\w\s-]", "", text).strip().lower()
        return re.sub(r"[-\s]+", "-", s)[:90]

    @staticmethod
    def _format_preview(val: Optional[str], prefix: str = "sec") -> Optional[str]:
        if not val:
            return None
        if len(val) <= 8:
            return f"{prefix}_****"
        return f"{val[:6]}****{val[-4:]}"

    def format_connection_response(
        self, conn: IntegrationConnection
    ) -> IntegrationConnectionResponse:
        slug_or_id = conn.slug or str(conn.id)
        webhook_url = f"/api/v1/integrations/webhooks/{slug_or_id}"

        return IntegrationConnectionResponse(
            id=conn.id,
            organization_id=conn.organization_id,
            name=conn.name,
            slug=conn.slug,
            integration_type=conn.integration_type,
            adapter_type=conn.adapter_type,
            is_active=conn.is_active,
            base_url=conn.base_url,
            webhook_url=webhook_url,
            webhook_secret_preview=self._format_preview(conn.webhook_secret, "whsec"),
            api_key_preview=self._format_preview(conn.api_key, "key"),
            health_status=conn.health_status,
            consecutive_failures=conn.consecutive_failures,
            stats=conn.stats or {},
            last_synced_at=conn.last_synced_at,
            sync_status=conn.sync_status,
            created_at=conn.created_at,
            updated_at=conn.updated_at,
        )

    async def list_connections(
        self, session: AsyncSession, organization_id: uuid.UUID
    ) -> List[IntegrationConnectionResponse]:
        stmt = (
            select(IntegrationConnection)
            .where(
                IntegrationConnection.organization_id == organization_id,
                IntegrationConnection.is_deleted == False,
            )
            .order_by(IntegrationConnection.created_at.desc())
        )
        conns = (await session.execute(stmt)).scalars().all()
        return [self.format_connection_response(c) for c in conns]

    async def get_connection(
        self, session: AsyncSession, organization_id: uuid.UUID, connection_id: uuid.UUID
    ) -> IntegrationConnectionResponse:
        stmt = select(IntegrationConnection).where(
            IntegrationConnection.id == connection_id,
            IntegrationConnection.organization_id == organization_id,
            IntegrationConnection.is_deleted == False,
        )
        conn = (await session.execute(stmt)).scalar_one_or_none()
        if not conn:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Integration connection '{connection_id}' not found.",
            )
        return self.format_connection_response(conn)

    async def create_connection(
        self,
        session: AsyncSession,
        organization_id: uuid.UUID,
        req: IntegrationConnectionCreate,
    ) -> IntegrationConnectionResponse:
        # Determine slug
        base_slug = self._slugify(req.slug or req.name)
        slug = base_slug
        
        # Check slug uniqueness within organization
        existing_stmt = select(IntegrationConnection).where(
            IntegrationConnection.organization_id == organization_id,
            IntegrationConnection.slug == slug,
            IntegrationConnection.is_deleted == False,
        )
        if (await session.execute(existing_stmt)).scalar_one_or_none():
            slug = f"{base_slug}-{uuid.uuid4().hex[:6]}"

        # Generate secrets if not supplied
        webhook_secret = req.webhook_secret or f"whsec_{secrets.token_hex(24)}"
        api_key = req.api_key

        conn = IntegrationConnection(
            organization_id=organization_id,
            name=req.name,
            slug=slug,
            integration_type=req.integration_type,
            adapter_type=req.adapter_type.upper(),
            base_url=req.base_url,
            auth_config=req.auth_config or {},
            headers=req.headers or {},
            webhook_secret=webhook_secret,
            api_key=api_key,
            is_active=req.is_active,
            health_status="HEALTHY",
            consecutive_failures=0,
            stats={"total_received": 0, "total_succeeded": 0, "total_failed": 0},
            sync_status="IDLE",
        )
        session.add(conn)
        await session.commit()
        await session.refresh(conn)
        return self.format_connection_response(conn)

    async def update_connection(
        self,
        session: AsyncSession,
        organization_id: uuid.UUID,
        connection_id: uuid.UUID,
        req: IntegrationConnectionUpdate,
    ) -> IntegrationConnectionResponse:
        stmt = select(IntegrationConnection).where(
            IntegrationConnection.id == connection_id,
            IntegrationConnection.organization_id == organization_id,
            IntegrationConnection.is_deleted == False,
        )
        conn = (await session.execute(stmt)).scalar_one_or_none()
        if not conn:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Integration connection '{connection_id}' not found.",
            )

        if req.name is not None:
            conn.name = req.name
        if req.slug is not None:
            conn.slug = self._slugify(req.slug)
        if req.integration_type is not None:
            conn.integration_type = req.integration_type
        if req.adapter_type is not None:
            conn.adapter_type = req.adapter_type.upper()
        if req.base_url is not None:
            conn.base_url = req.base_url
        if req.auth_config is not None:
            conn.auth_config = req.auth_config
        if req.headers is not None:
            conn.headers = req.headers
        if req.webhook_secret is not None and req.webhook_secret.strip():
            conn.webhook_secret = req.webhook_secret.strip()
        if req.api_key is not None and req.api_key.strip():
            conn.api_key = req.api_key.strip()
        if req.is_active is not None:
            conn.is_active = req.is_active

        conn.updated_at = datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(conn)
        return self.format_connection_response(conn)

    async def delete_connection(
        self, session: AsyncSession, organization_id: uuid.UUID, connection_id: uuid.UUID
    ) -> None:
        stmt = select(IntegrationConnection).where(
            IntegrationConnection.id == connection_id,
            IntegrationConnection.organization_id == organization_id,
            IntegrationConnection.is_deleted == False,
        )
        conn = (await session.execute(stmt)).scalar_one_or_none()
        if not conn:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Integration connection '{connection_id}' not found.",
            )

        conn.is_deleted = True
        conn.deleted_at = datetime.now(timezone.utc)
        await session.commit()

    async def regenerate_webhook_secret(
        self, session: AsyncSession, organization_id: uuid.UUID, connection_id: uuid.UUID
    ) -> dict:
        """
        Regenerates webhook signing secret. Returns the raw secret ONCE in response for the user to record.
        """
        stmt = select(IntegrationConnection).where(
            IntegrationConnection.id == connection_id,
            IntegrationConnection.organization_id == organization_id,
            IntegrationConnection.is_deleted == False,
        )
        conn = (await session.execute(stmt)).scalar_one_or_none()
        if not conn:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Integration connection '{connection_id}' not found.",
            )

        new_secret = f"whsec_{secrets.token_hex(24)}"
        conn.webhook_secret = new_secret
        conn.updated_at = datetime.now(timezone.utc)
        await session.commit()

        return {
            "connection_id": str(conn.id),
            "webhook_secret": new_secret,
            "message": "Store this webhook secret safely. It will not be shown again in full.",
        }


registry_service = IntegrationRegistryService()
