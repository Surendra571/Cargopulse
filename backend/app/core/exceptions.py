from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import logging

logger = logging.getLogger("cargopulse.exceptions")


class ErrorDetail(BaseModel):
    field: Optional[str] = None
    issue: str


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: Optional[List[ErrorDetail]] = None
    trace_id: Optional[str] = None


class UnifiedErrorEnvelope(BaseModel):
    success: bool = False
    error: ErrorResponse
    meta: Dict[str, Any]


class AppException(Exception):
    """
    Base application exception with standardized code and HTTP status.
    """
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: Optional[List[ErrorDetail]] = None,
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details
        super().__init__(message)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        logger.warning(f"AppException: {exc.code} - {exc.message} on {request.url.path}")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": [d.model_dump() for d in exc.details] if exc.details else None,
                },
                "meta": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "path": request.url.path,
                },
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        details = []
        for error in exc.errors():
            field_name = ".".join(str(loc) for loc in error.get("loc", []))
            details.append({"field": field_name, "issue": error.get("msg", "Invalid value")})

        logger.info(f"Validation error on {request.url.path}: {details}")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Input validation failed. Inspect details for fields.",
                    "details": details,
                },
                "meta": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "path": request.url.path,
                },
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error(f"Unhandled error on {request.url.path}: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected server error occurred. Our engineering team has been notified.",
                },
                "meta": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "path": request.url.path,
                },
            },
        )
