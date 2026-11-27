import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from app.schemas.integrations import NormalizedEvent
from app.services.integrations.adapters.base import BaseTransporterAdapter


class SamsaraTelematicsAdapter(BaseTransporterAdapter):
    """
    Adapter for Samsara Telematics webhook feeds.
    Samsara payload structure:
    {
      "eventId": "sam_evt_991823",
      "eventType": "LocationUpdate",
      "happenedAtTime": "2026-11-25T14:30:00Z",
      "vehicle": {
        "id": "28147497912345",
        "name": "MH12AB1234"
      },
      "location": {
        "latitude": 18.5204,
        "longitude": 73.8567,
        "headingDegrees": 180,
        "speedMilesPerHour": 45.5,
        "reverseGeo": {
          "formattedLocation": "Pune Bypass Rd, Pune, MH"
        }
      }
    }
    """

    @property
    def adapter_type(self) -> str:
        return "SAMSARA"

    @property
    def name(self) -> str:
        return "Samsara Telematics Adapter"

    def verify_signature(
        self,
        payload_bytes: bytes,
        headers: Dict[str, str],
        secret: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> bool:
        # Check X-API-Key or Bearer token
        req_api_key = headers.get("x-api-key") or headers.get("X-API-Key")
        if api_key and req_api_key:
            import hmac
            if hmac.compare_digest(req_api_key.strip(), api_key.strip()):
                return True

        # Check Samsara signature header
        sig_header = (
            headers.get("x-samsara-signature")
            or headers.get("X-Samsara-Signature")
            or headers.get("x-hub-signature-256")
            or headers.get("X-Hub-Signature-256")
        )
        if not secret or not sig_header:
            return False

        ts_header = headers.get("x-samsara-timestamp") or headers.get("X-Samsara-Timestamp")
        if not self.verify_timestamp_drift(ts_header, max_drift_seconds=300):
            return False

        return self.secure_compare_hmac(secret, payload_bytes, sig_header)

    def extract_identity(
        self,
        payload: Dict[str, Any],
        headers: Dict[str, str],
    ) -> Tuple[Optional[str], Optional[datetime]]:
        event_id = payload.get("eventId") or payload.get("id") or headers.get("x-event-id")
        
        occurred_at = None
        ts_str = payload.get("happenedAtTime") or payload.get("time") or payload.get("timestamp")
        if ts_str:
            try:
                occurred_at = datetime.fromisoformat(str(ts_str).replace("Z", "+00:00"))
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
            event_id = f"sam_{uuid.uuid4().hex[:12]}"
        if not occurred_at:
            occurred_at = datetime.now(timezone.utc)

        vehicle_data = payload.get("vehicle") or {}
        location_data = payload.get("location") or {}

        lat = location_data.get("latitude")
        lon = location_data.get("longitude")
        speed_mph = float(location_data.get("speedMilesPerHour") or 0.0)
        speed_kmh = round(speed_mph * 1.60934, 1)

        reverse_geo = location_data.get("reverseGeo") or {}
        loc_name = reverse_geo.get("formattedLocation") or location_data.get("formattedAddress")

        veh_plate = vehicle_data.get("name") or vehicle_data.get("licensePlate") or ""
        veh_ext_id = vehicle_data.get("id")

        return NormalizedEvent(
            event_id=str(event_id),
            event_type="LOCATION_PING",
            tracking_number=str(payload.get("trackingNumber") or payload.get("tracking_number") or ""),
            vehicle_id=str(veh_ext_id) if veh_ext_id else None,
            vehicle_registration=veh_plate,
            occurred_at=occurred_at,
            latitude=float(lat) if lat is not None else None,
            longitude=float(lon) if lon is not None else None,
            location_name=loc_name,
            speed_kmh=speed_kmh,
            status="IN_TRANSIT" if speed_kmh > 5 else "STATIONARY",
            notes=f"Samsara GPS Update: Vehicle {veh_plate}",
            raw_payload=payload,
            metadata={"heading": location_data.get("headingDegrees"), "vehicle_id": veh_ext_id},
        )
