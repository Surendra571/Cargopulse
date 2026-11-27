import hashlib
import hmac
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from fastapi import HTTPException, UploadFile, status

from app.core.config import settings

logger = logging.getLogger("cargopulse.storage")

# Disallowed dangerous extensions
DANGEROUS_EXTENSIONS = {
    ".exe", ".bat", ".cmd", ".sh", ".bash", ".py", ".pl", ".php",
    ".js", ".vbs", ".scr", ".pif", ".msi", ".jar", ".ps1"
}


class StorageService:
    """
    S3-compatible object storage provider with graceful local fallback.
    Stores secure object references, enforces MIME type and size checks,
    computes SHA-256 integrity hashes, and creates controlled-access URLs.
    """

    def __init__(self):
        self.backend = settings.STORAGE_BACKEND.lower()
        self.bucket = settings.S3_BUCKET_NAME
        self.local_dir = Path(settings.LOCAL_STORAGE_DIR).resolve()
        self.local_dir.mkdir(parents=True, exist_ok=True)
        self._s3_client = None

        if self.backend == "s3" or settings.S3_ACCESS_KEY_ID:
            try:
                import boto3
                from botocore.config import Config

                boto_config = Config(
                    signature_version="s3v4",
                    retries={"max_attempts": 3, "mode": "standard"},
                )
                self._s3_client = boto3.client(
                    "s3",
                    endpoint_url=settings.S3_ENDPOINT_URL,
                    region_name=settings.S3_REGION_NAME,
                    aws_access_key_id=settings.S3_ACCESS_KEY_ID,
                    aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
                    config=boto_config,
                )
                logger.info("Initialized S3 object storage client successfully.")
            except Exception as e:
                logger.warning(f"Could not initialize S3 client: {e}. Falling back to local secure storage.")
                self.backend = "local"

    def validate_file(self, file_name: str, content_type: str, file_size: int) -> None:
        """
        Validates that uploaded file meets security standards:
        - Within MAX_UPLOAD_SIZE_BYTES limit (10MB)
        - Allowed image or PDF MIME types
        - Prohibits executable or script file extensions
        """
        if file_size > settings.MAX_UPLOAD_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)}MB.",
            )

        # Normalize content type
        norm_type = content_type.lower().split(";")[0].strip()
        if norm_type not in [m.lower() for m in settings.ALLOWED_MIME_TYPES]:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"Unsupported file type '{norm_type}'. Allowed types: {', '.join(settings.ALLOWED_MIME_TYPES)}",
            )

        ext = Path(file_name).suffix.lower()
        if ext in DANGEROUS_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File extension '{ext}' is prohibited for security reasons.",
            )

    def _sanitize_filename(self, file_name: str) -> str:
        clean = re.sub(r"[^a-zA-Z0-9_\.-]", "_", Path(file_name).name)
        return clean or "upload.bin"

    def _generate_hmac_token(self, file_key: str, expires_at: int) -> str:
        msg = f"{file_key}:{expires_at}"
        return hmac.new(settings.SECRET_KEY.encode(), msg.encode(), hashlib.sha256).hexdigest()

    def verify_hmac_token(self, file_key: str, expires_at: int, token: str) -> bool:
        if datetime.now(timezone.utc).timestamp() > expires_at:
            return False
        expected = self._generate_hmac_token(file_key, expires_at)
        return hmac.compare_digest(expected, token)

    def generate_controlled_access_url(self, file_key: str, expires_in_seconds: int = 86400) -> str:
        """
        Generates controlled-access URL. If S3, returns an S3 presigned URL;
        otherwise returns an authenticated signed API endpoint URL.
        """
        if self._s3_client and self.backend == "s3":
            try:
                return self._s3_client.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": self.bucket, "Key": file_key},
                    ExpiresIn=expires_in_seconds,
                )
            except Exception as exc:
                logger.error(f"Failed to generate S3 presigned URL for {file_key}: {exc}")

        # Local controlled-access fallback URL
        expires_at = int(datetime.now(timezone.utc).timestamp() + expires_in_seconds)
        token = self._generate_hmac_token(file_key, expires_at)
        return f"{settings.API_V1_PREFIX}/pod/files/download?file_key={file_key}&expires={expires_at}&token={token}"

    async def upload_file_bytes(
        self,
        data: bytes,
        file_name: str,
        content_type: str,
        organization_id: uuid.UUID,
        shipment_id: uuid.UUID,
        category: str = "delivery_photo",
    ) -> Dict[str, Any]:
        """
        Validates and stores binary file payload. Generates a secure unique object key,
        stores SHA-256 integrity hash, and returns file metadata reference.
        """
        self.validate_file(file_name, content_type, len(data))

        clean_name = self._sanitize_filename(file_name)
        file_hash = hashlib.sha256(data).hexdigest()
        unique_id = uuid.uuid4().hex[:12]
        object_key = f"pod/{organization_id}/{shipment_id}/{unique_id}_{clean_name}"

        storage_provider = "local_secure"

        if self._s3_client and self.backend == "s3":
            try:
                self._s3_client.put_object(
                    Bucket=self.bucket,
                    Key=object_key,
                    Body=data,
                    ContentType=content_type,
                    Metadata={
                        "sha256": file_hash,
                        "organization_id": str(organization_id),
                        "shipment_id": str(shipment_id),
                        "category": category,
                    },
                )
                storage_provider = "s3"
                logger.info(f"Uploaded {object_key} to S3 bucket '{self.bucket}'.")
            except Exception as e:
                logger.error(f"Failed S3 put_object for {object_key}: {e}. Falling back to disk.")
                storage_provider = "local_secure"

        if storage_provider == "local_secure":
            target_path = self.local_dir / object_key
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with open(target_path, "wb") as f:
                f.write(data)

        access_url = self.generate_controlled_access_url(object_key)

        return {
            "file_key": object_key,
            "file_name": clean_name,
            "content_type": content_type,
            "file_size_bytes": len(data),
            "sha256_hash": file_hash,
            "storage_provider": storage_provider,
            "url": access_url,
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
            "category": category,
        }

    def get_file_bytes(self, file_key: str) -> Tuple[bytes, str]:
        """
        Retrieves file bytes and content type by key from storage provider.
        """
        if self._s3_client and self.backend == "s3":
            try:
                resp = self._s3_client.get_object(Bucket=self.bucket, Key=file_key)
                content_type = resp.get("ContentType", "application/octet-stream")
                data = resp["Body"].read()
                return data, content_type
            except Exception as e:
                logger.warning(f"Failed to fetch {file_key} from S3: {e}. Checking local disk.")

        local_path = self.local_dir / file_key
        if not local_path.is_file():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Storage object '{file_key}' not found.",
            )

        with open(local_path, "rb") as f:
            data = f.read()

        ext = local_path.suffix.lower()
        content_type_map = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
            ".pdf": "application/pdf",
        }
        content_type = content_type_map.get(ext, "application/octet-stream")
        return data, content_type


# Global singleton storage instance
storage_service = StorageService()
