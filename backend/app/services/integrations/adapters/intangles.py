import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from app.schemas.integrations import NormalizedEvent
from app.services.integrations.adapters.base import BaseTransporterAdapter


class IntanglesTelematicsAdapter(BaseTransporterAdapter):
    """
    Adapter for Intangles Telematics & IoT Platform.
    Intangles payload structure:
    {
      "packet_id": "INT_PKT_882190",
      "event_type": "TELEMATICS_PING",
      "timestamp": 1732545000,
      "vehicle_number": "KA01MJ9988",
      "gps": {
        "lat": 12.9716,
        "lon": 77.5946,
        "address": "Hosur Road, Bengaluru, KA",
        "speed": 62.4
      },
      "fuel_level": 74.2,
      "engine_status": "RUNNING"
    }
    """

    @property
    def adapter_type(self) -> str:
        return "INTANGLES"

    @property
    def name(self) -> str:
        return "Intangles Telematics Adapter"

    def verify_signature(
        self,
        payload_bytes: bytes,
        headers: Dict[str, str],
        secret: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> bool:
        # Check API key / Auth token header
        req_token = headers.get("x-auth-token") or headers.get("X-Auth-Token") or headers.get("x-api-key")
        if api_key and req_token:
            import hmac
            if hmac.compare_digest(req_token.strip(), api_key.strip()):
                return True

        sig_header = headers.get("x-intangles-signature") or headers.get("X-Intangles-Signature")
        if not secret or not sig_header:
            return False

        ts_header = headers.get("x-intangles-timestamp") or headers.get("X-Intangles-Timestamp")
        if not self.verify_timestamp_drift(ts_header, max_drift_seconds=300):
            return False

        return self.secure_compare_hmac(secret, payload_bytes, sig_header)

    def extract_identity(
        self,
        payload: Dict[str, Any],
        headers: Dict[str, str],
    ) -> Tuple[Optional[str], Optional[datetime]]:
        event_id = payload.get("packet_id") or payload.get("alert_id") or payload.get("id")
        
        occurred_at = None
        ts = payload.get("timestamp") or payload.get("epoch_time")
        if ts is not None:
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
            event_id = f"int_{uuid.uuid4().hex[:12]}"
        if not occurred_at:
            occurred_at = datetime.now(timezone.utc)

        gps = payload.get("gps") or {}
        lat = gps.get("lat") or payload.get("latitude")
        lon = gps.get("lon") or payload.get("longitude")
        speed = float(gps.get("speed") or payload.get("speed_kmph") or 0.0)
        loc_name = gps.get("address") or payload.get("location_name")
        veh_num = payload.get("vehicle_number") or payload.get("reg_no") or ""

        return NormalizedEvent(
            event_id=str(event_id),
            event_type="LOCATION_PING",
            tracking_number=str(payload.get("lr_number") or payload.get("tracking_number") or ""),
            vehicle_registration=veh_num,
            occurred_at=occurred_at,
            latitude=float(lat) if lat is not None else None,
            longitude=float(lon) if lon is not None else None,
            location_name=loc_name,
            speed_kmh=speed,
            status="IN_TRANSIT" if speed > 5 else "IDLE",
            notes=f"Intangles Telematics: {veh_num} at {speed} km/h",
            raw_payload=payload,
            metadata={"engine_status": payload.get("engine_status"), "fuel_level": payload.get("fuel_level")},
        )
