import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from app.schemas.integrations import NormalizedEvent
from app.services.integrations.adapters.base import BaseTransporterAdapter


class GenericWebhookAdapter(BaseTransporterAdapter):
    """
    Standard native CargoPulse webhook adapter.
    Accepts standardized JSON payloads authenticated with HMAC-SHA256 signature
    in `X-CargoPulse-Signature` or API key in `X-API-Key`.
    """

    @property
    def adapter_type(self) -> str:
        return "GENERIC"

    @property
    def name(self) -> str:
        return "CargoPulse Generic Webhook Adapter"

    def verify_signature(
        self,
        payload_bytes: bytes,
        headers: Dict[str, str],
        secret: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> bool:
        # 1. API Key Authentication
        req_api_key = headers.get("x-api-key") or headers.get("X-API-Key")
        if api_key and req_api_key:
            import hmac
            if hmac.compare_digest(req_api_key.strip(), api_key.strip()):
                return True

        # 2. HMAC Signature Authentication
        sig_header = (
            headers.get("x-cargopulse-signature")
            or headers.get("X-CargoPulse-Signature")
            or headers.get("x-signature")
            or headers.get("X-Signature")
        )
        if not secret or not sig_header:
            return False

        # Anti-replay timestamp check
        ts_header = headers.get("x-cargopulse-timestamp") or headers.get("X-CargoPulse-Timestamp")
        if not self.verify_timestamp_drift(ts_header, max_drift_seconds=300):
            return False

        return self.secure_compare_hmac(secret, payload_bytes, sig_header)

    def extract_identity(
        self,
        payload: Dict[str, Any],
        headers: Dict[str, str],
    ) -> Tuple[Optional[str], Optional[datetime]]:
        event_id = payload.get("event_id") or payload.get("id") or headers.get("x-event-id") or headers.get("X-Event-ID")
        
        occurred_at = None
        ts = payload.get("occurred_at") or payload.get("timestamp")
        if ts:
            try:
                if isinstance(ts, (int, float)):
                    if ts > 1e11:
                        ts = ts / 1000.0
                    occurred_at = datetime.fromtimestamp(ts, tz=timezone.utc)
                elif isinstance(ts, str):
                    occurred_at = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except Exception:
                occurred_at = datetime.now(timezone.utc)

        return event_id, occurred_at

    def normalize_event(
        self,
        payload: Dict[str, Any],
        headers: Dict[str, str],
    ) -> NormalizedEvent:
        event_id, occurred_at = self.extract_identity(payload, headers)
        if not event_id:
            event_id = f"gen_{uuid.uuid4().hex[:12]}"
        if not occurred_at:
            occurred_at = datetime.now(timezone.utc)

        # Coordinate extraction
        lat = payload.get("latitude")
        lon = payload.get("longitude")
        if lat is not None:
            lat = float(lat)
        if lon is not None:
            lon = float(lon)

        event_type = payload.get("event_type") or payload.get("event_name") or "LOCATION_PING"

        eta = None
        if payload.get("estimated_delivery_at"):
            try:
                eta = datetime.fromisoformat(str(payload.get("estimated_delivery_at")).replace("Z", "+00:00"))
            except Exception:
                pass

        return NormalizedEvent(
            event_id=str(event_id),
            event_type=str(event_type),
            shipment_id=str(payload.get("shipment_id")) if payload.get("shipment_id") else None,
            tracking_number=str(payload.get("tracking_number")) if payload.get("tracking_number") else None,
            vehicle_id=str(payload.get("vehicle_id")) if payload.get("vehicle_id") else None,
            vehicle_registration=str(payload.get("vehicle_registration") or payload.get("vehicle_number") or ""),
            driver_phone=str(payload.get("driver_phone")) if payload.get("driver_phone") else None,
            occurred_at=occurred_at,
            latitude=lat,
            longitude=lon,
            location_name=payload.get("location_name") or payload.get("address"),
            speed_kmh=float(payload.get("speed_kmh") or payload.get("speed") or 0.0),
            estimated_delivery_at=eta,
            milestone=payload.get("milestone"),
            status=payload.get("status"),
            notes=payload.get("notes") or payload.get("description"),
            raw_payload=payload,
            metadata=payload.get("metadata") or {},
        )
