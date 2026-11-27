import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from app.schemas.integrations import NormalizedEvent
from app.services.integrations.adapters.base import BaseTransporterAdapter


class CustomERPAdapter(BaseTransporterAdapter):
    """
    Adapter for Customer ERP systems (SAP S/4HANA, Oracle TMS, Microsoft Dynamics 365).
    Payload structure:
    {
      "message_id": "MSG_SAP_009817",
      "document_number": "DOC-908123",
      "customer_reference": "PO-2026-4491",
      "tracking_number": "TRK-2026-0001",
      "timestamp": "2026-11-25T14:45:00Z",
      "status_code": "DISPATCH_CONFIRMED",
      "plant": "PLANT-IN-101",
      "estimated_arrival": "2026-11-27T18:00:00Z",
      "remarks": "Goods issued from central warehouse."
    }
    """

    @property
    def adapter_type(self) -> str:
        return "CUSTOM_ERP"

    @property
    def name(self) -> str:
        return "Enterprise ERP Adapter (SAP / Oracle TMS)"

    def verify_signature(
        self,
        payload_bytes: bytes,
        headers: Dict[str, str],
        secret: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> bool:
        # Check API key / Bearer
        req_key = headers.get("x-api-key") or headers.get("X-API-Key")
        auth_hdr = headers.get("authorization") or headers.get("Authorization")
        if auth_hdr and auth_hdr.startswith("Bearer "):
            bearer = auth_hdr.split(" ")[1]
            if api_key:
                import hmac
                return hmac.compare_digest(bearer.strip(), api_key.strip())

        if api_key and req_key:
            import hmac
            if hmac.compare_digest(req_key.strip(), api_key.strip()):
                return True

        sig_header = headers.get("x-erp-signature") or headers.get("X-ERP-Signature")
        if not secret or not sig_header:
            return False

        ts_header = headers.get("x-erp-timestamp") or headers.get("X-ERP-Timestamp")
        if not self.verify_timestamp_drift(ts_header, max_drift_seconds=300):
            return False

        return self.secure_compare_hmac(secret, payload_bytes, sig_header)

    def extract_identity(
        self,
        payload: Dict[str, Any],
        headers: Dict[str, str],
    ) -> Tuple[Optional[str], Optional[datetime]]:
        event_id = payload.get("message_id") or payload.get("id") or payload.get("document_number")
        
        occurred_at = None
        ts = payload.get("timestamp") or payload.get("date_time")
        if ts:
            try:
                occurred_at = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
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
            event_id = f"erp_{uuid.uuid4().hex[:12]}"
        if not occurred_at:
            occurred_at = datetime.now(timezone.utc)

        status_code = str(payload.get("status_code") or "").upper()
        # Map ERP status code to CargoPulse milestone / event type
        milestone = None
        event_type = "MILESTONE_UPDATE"

        if "DISPATCH" in status_code or "ISSUED" in status_code:
            milestone = "IN_TRANSIT"
        elif "DELIVERED" in status_code or "POD" in status_code:
            milestone = "DELIVERED"
        elif "ARRIVAL" in status_code:
            milestone = "CHECKPOINT_REACHED"
        elif "CREATED" in status_code:
            milestone = "SHIPMENT_CREATED"

        eta = None
        if payload.get("estimated_arrival") or payload.get("expected_delivery"):
            try:
                eta = datetime.fromisoformat(
                    str(payload.get("estimated_arrival") or payload.get("expected_delivery")).replace("Z", "+00:00")
                )
            except Exception:
                pass

        return NormalizedEvent(
            event_id=str(event_id),
            event_type=event_type,
            tracking_number=str(payload.get("tracking_number") or payload.get("customer_reference") or ""),
            occurred_at=occurred_at,
            estimated_delivery_at=eta,
            milestone=milestone,
            status=status_code,
            location_name=payload.get("plant") or payload.get("location"),
            notes=payload.get("remarks") or f"ERP Status Update: {status_code}",
            raw_payload=payload,
            metadata={"plant": payload.get("plant"), "doc_number": payload.get("document_number")},
        )
