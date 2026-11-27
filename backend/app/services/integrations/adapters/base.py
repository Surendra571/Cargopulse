import hashlib
import hmac
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from app.schemas.integrations import NormalizedEvent


class BaseTransporterAdapter(ABC):
    """
    Abstract base class for external transporter and ERP integration adapters.
    Provides signature verification, payload normalization, and event identity extraction.
    """

    @property
    @abstractmethod
    def adapter_type(self) -> str:
        """Unique adapter type identifier (e.g. GENERIC, SAMSARA, INTANGLES, CUSTOM_ERP)."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable adapter name."""
        pass

    @abstractmethod
    def verify_signature(
        self,
        payload_bytes: bytes,
        headers: Dict[str, str],
        secret: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> bool:
        """
        Verify incoming webhook signature and authentication headers.
        Uses constant-time comparison to prevent timing attacks.
        """
        pass

    @abstractmethod
    def normalize_event(
        self,
        payload: Dict[str, Any],
        headers: Dict[str, str],
    ) -> NormalizedEvent:
        """
        Normalize vendor-specific payload into standard CargoPulse NormalizedEvent.
        """
        pass

    @abstractmethod
    def extract_identity(
        self,
        payload: Dict[str, Any],
        headers: Dict[str, str],
    ) -> Tuple[Optional[str], Optional[datetime]]:
        """
        Extract unique vendor event ID and occurrence timestamp for deduplication.
        Returns (external_event_id, occurred_at).
        """
        pass

    @staticmethod
    def secure_compare_hmac(key: str, data: bytes, expected_signature: str) -> bool:
        """
        Computes HMAC-SHA256 of data using key and performs constant-time compare against expected signature.
        """
        if not key or not expected_signature:
            return False
        
        # Remove sha256= prefix if present
        clean_sig = expected_signature.strip()
        if clean_sig.startswith("sha256="):
            clean_sig = clean_sig[7:]

        mac = hmac.new(key.encode("utf-8"), data, hashlib.sha256)
        computed_sig = mac.hexdigest()
        return hmac.compare_digest(computed_sig.lower(), clean_sig.lower())

    @staticmethod
    def verify_timestamp_drift(
        timestamp_header: Optional[str],
        max_drift_seconds: int = 300,
    ) -> bool:
        """
        Validates timestamp against current UTC time to prevent replay attacks.
        Allows up to max_drift_seconds in the past or future.
        """
        if not timestamp_header:
            return True  # If no timestamp header is provided, pass timestamp check
        
        try:
            # Check epoch timestamp (seconds or milliseconds)
            ts_val = float(timestamp_header)
            if ts_val > 1e11:  # milliseconds
                ts_val = ts_val / 1000.0
            
            now_epoch = time.time()
            drift = abs(now_epoch - ts_val)
            return drift <= max_drift_seconds
        except (ValueError, TypeError):
            # Try ISO format
            try:
                dt = datetime.fromisoformat(timestamp_header.replace("Z", "+00:00"))
                now_dt = datetime.now(timezone.utc)
                drift = abs((now_dt - dt).total_seconds())
                return drift <= max_drift_seconds
            except Exception:
                return False
