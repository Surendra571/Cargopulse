import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.integrations import AuditLog, IntegrationConnection, WebhookEvent
from app.schemas.integrations import WebhookIngestResponse
from app.services.integrations.adapters import adapter_registry

logger = logging.getLogger(__name__)


class WebhookService:
    """
    Ingestion, authentication, deduplication, and persistence of incoming webhooks.
    """

    @staticmethod
    def _sanitize_headers(headers: Dict[str, str]) -> Dict[str, str]:
        """
        Strips authentication tokens and signing secrets before persisting headers.
        """
        sensitive_keys = {
            "authorization", "x-api-key", "x-cargopulse-signature",
            "x-signature", "x-samsara-signature", "x-intangles-signature",
            "x-erp-signature", "cookie", "set-cookie", "x-auth-token"
        }
        sanitized = {}
        for k, v in headers.items():
            if k.lower() in sensitive_keys:
                sanitized[k] = "[REDACTED]"
            else:
                sanitized[k] = v
        return sanitized

    async def get_connection_by_slug_or_id(
        self, session: AsyncSession, identifier: str
    ) -> Optional[IntegrationConnection]:
        """
        Resolves active integration connection by UUID or unique slug.
        """
        stmt = select(IntegrationConnection).where(
            IntegrationConnection.is_deleted == False
        )
        try:
            val_uuid = uuid.UUID(identifier)
            stmt = stmt.where(
                or_(
                    IntegrationConnection.id == val_uuid,
                    IntegrationConnection.slug == identifier,
                )
            )
        except ValueError:
            stmt = stmt.where(IntegrationConnection.slug == identifier)

        res = await session.execute(stmt)
        return res.scalars().first()

    async def ingest_webhook(
        self,
        session: AsyncSession,
        identifier: str,
        payload_bytes: bytes,
        headers: Dict[str, str],
        client_ip: Optional[str] = None,
    ) -> WebhookIngestResponse:
        """
        1. Resolve integration
        2. Authenticate source (signature / API key)
        3. Parse JSON payload
        4. Normalize event
        5. Extract identity & deduplicate
        6. Persist incoming webhook event
        7. Acknowledge receipt
        """
        # 1. Identify Integration
        connection = await self.get_connection_by_slug_or_id(session, identifier)
        if not connection:
            logger.warning(f"Webhook ingestion rejected: Integration '{identifier}' not found.")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Integration '{identifier}' not found or inactive.",
            )

        if not connection.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Integration '{connection.name}' is currently deactivated.",
            )

        # 2. Resolve Adapter
        adapter = adapter_registry.get_adapter(connection.adapter_type)

        # 3. Authenticate Source & Validate Signature
        is_valid = adapter.verify_signature(
            payload_bytes=payload_bytes,
            headers=headers,
            secret=connection.webhook_secret,
            api_key=connection.api_key,
        )

        if not is_valid:
            # Update connection failure stats
            connection.consecutive_failures += 1
            if connection.consecutive_failures >= 3:
                connection.health_status = "CRITICAL"
            elif connection.consecutive_failures >= 1:
                connection.health_status = "DEGRADED"

            stats = dict(connection.stats or {})
            stats["last_auth_failure_at"] = datetime.now(timezone.utc).isoformat()
            stats["total_auth_failures"] = stats.get("total_auth_failures", 0) + 1
            connection.stats = stats

            # Record security audit log (WITHOUT secrets!)
            audit = AuditLog(
                organization_id=connection.organization_id,
                action="WEBHOOK_AUTH_FAILED",
                entity_name="IntegrationConnection",
                entity_id=connection.id,
                ip_address=client_ip,
                changes={"reason": "Invalid signature or expired timestamp", "adapter": adapter.adapter_type},
            )
            session.add(audit)
            await session.commit()

            logger.warning(
                f"Unauthorized webhook attempt on connection {connection.id} ({connection.name}) from IP {client_ip}"
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature, timestamp, or authentication header.",
            )

        # 4. Parse Payload
        try:
            payload_dict = json.loads(payload_bytes.decode("utf-8"))
            if not isinstance(payload_dict, dict):
                raise ValueError("Payload must be a JSON object")
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid JSON payload: {str(e)}",
            )

        # 5. Normalize Event via Adapter
        try:
            normalized = adapter.normalize_event(payload_dict, headers)
        except Exception as e:
            logger.error(f"Failed to normalize webhook event: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Failed to normalize webhook event format: {str(e)}",
            )

        # 6. Extract Identity & Deduplication Check
        external_event_id, occurred_at = adapter.extract_identity(payload_dict, headers)
        provider_name = adapter.adapter_type.lower()

        # Compute deterministic idempotency key
        if external_event_id:
            idempotency_key = f"{provider_name}:{external_event_id}"
        else:
            payload_hash = hashlib.sha256(payload_bytes).hexdigest()[:32]
            idempotency_key = f"{provider_name}:hash_{payload_hash}"

        # Deduplicate using provider and event identity
        dup_stmt = select(WebhookEvent).where(
            or_(
                WebhookEvent.idempotency_key == idempotency_key,
                (
                    (WebhookEvent.provider == provider_name)
                    & (WebhookEvent.external_event_id == external_event_id)
                    & (WebhookEvent.external_event_id.isnot(None))
                ),
            )
        )
        existing = (await session.execute(dup_stmt)).scalars().first()
        if existing:
            # Acknowledge duplicate without creating duplicate business effects
            logger.info(
                f"Duplicate webhook received for provider '{provider_name}' ID '{external_event_id}'. "
                f"Status: {existing.status}."
            )
            return WebhookIngestResponse(
                status="DUPLICATE_ACKNOWLEDGED",
                event_id=str(existing.id),
                message="Event previously received. Duplicate acknowledged idempotently.",
            )

        # 7. Persist Incoming Webhook Event
        sanitized_headers = self._sanitize_headers(headers)
        webhook_event = WebhookEvent(
            organization_id=connection.organization_id,
            integration_id=connection.id,
            provider=provider_name,
            source=adapter.adapter_type,
            event_name=normalized.event_type,
            external_event_id=external_event_id,
            idempotency_key=idempotency_key,
            headers=sanitized_headers,
            payload=payload_dict,
            normalized_payload=normalized.model_dump(mode="json"),
            status="RECEIVED",
            max_retries=5,
            retry_count=0,
            is_dead_letter=False,
        )
        session.add(webhook_event)

        # Update Connection Statistics
        connection.last_synced_at = datetime.now(timezone.utc)
        connection.consecutive_failures = 0
        if connection.health_status != "HEALTHY":
            connection.health_status = "HEALTHY"

        stats = dict(connection.stats or {})
        stats["total_received"] = stats.get("total_received", 0) + 1
        stats["last_received_at"] = datetime.now(timezone.utc).isoformat()
        connection.stats = stats

        await session.commit()
        await session.refresh(webhook_event)

        logger.info(
            f"Successfully ingested webhook event {webhook_event.id} ({provider_name}:{external_event_id})"
        )
        return WebhookIngestResponse(
            status="RECEIVED",
            event_id=str(webhook_event.id),
            message="Webhook event accepted and persisted for reliable background processing.",
        )


webhook_service = WebhookService()
