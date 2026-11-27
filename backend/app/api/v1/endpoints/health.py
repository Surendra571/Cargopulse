from datetime import datetime, timezone
from fastapi import APIRouter, Response, status
from app.core.config import settings
from app.core.database import check_db_health
from app.core.redis import check_redis_health

router = APIRouter(prefix="/healthz", tags=["Health & Diagnostics"])


@router.get("", status_code=status.HTTP_200_OK)
async def get_health_overview():
    """
    Returns high-level system diagnostic overview including database and cache status.
    """
    db_health = await check_db_health()
    redis_health = await check_redis_health()

    is_healthy = db_health.get("connected", False) and redis_health.get("connected", False)
    status_str = "healthy" if is_healthy else "degraded"

    return {
        "success": True,
        "data": {
            "status": status_str,
            "application": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
            "services": {
                "database": db_health,
                "redis": redis_health,
            },
        },
        "meta": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }


@router.get("/live", status_code=status.HTTP_200_OK)
async def liveness_probe():
    """
    Kubernetes / Docker liveness probe confirming process is active.
    """
    return {"status": "alive", "timestamp": datetime.now(timezone.utc).isoformat()}


@router.get("/ready")
async def readiness_probe(response: Response):
    """
    Kubernetes / Docker readiness probe checking if upstream dependencies are accessible.
    Returns HTTP 200 when ready, HTTP 503 when degraded.
    """
    db_health = await check_db_health()
    redis_health = await check_redis_health()

    is_ready = db_health.get("connected", False) and redis_health.get("connected", False)

    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "ready": is_ready,
        "database": db_health.get("connected", False),
        "redis": redis_health.get("connected", False),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
