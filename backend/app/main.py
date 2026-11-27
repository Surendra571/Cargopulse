from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.logging import logger, setup_logging
from app.core.exceptions import register_exception_handlers
from app.core.redis import close_redis_pool
from app.api.v1.router import api_router


def _init_error_monitoring() -> None:
    """Initialize optional Sentry error monitoring when SENTRY_DSN is configured."""
    if not settings.SENTRY_DSN:
        return
    try:
        import sentry_sdk  # type: ignore

        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.ENVIRONMENT,
            release=f"{settings.APP_NAME}@{settings.APP_VERSION}",
            traces_sample_rate=0.1,
        )
        logger.info("Sentry error monitoring initialized.")
    except ImportError:
        logger.warning("SENTRY_DSN is set, but sentry-sdk is not installed.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup sequence
    setup_logging()
    settings.validate_production_settings()
    _init_error_monitoring()
    logger.info(
        f"Starting {settings.APP_NAME} v{settings.APP_VERSION} in [{settings.ENVIRONMENT}] mode"
    )
    yield
    # Shutdown sequence
    logger.info(f"Shutting down {settings.APP_NAME}...")
    await close_redis_pool()


def create_application() -> FastAPI:
    is_prod = settings.ENVIRONMENT.lower() == "production" and not settings.DEBUG
    app = FastAPI(
        title=f"{settings.APP_NAME} API",
        version=settings.APP_VERSION,
        description="Accountable B2B Logistics Platform API",
        openapi_url=None if is_prod else f"{settings.API_V1_PREFIX}/openapi.json",
        docs_url=None if is_prod else f"{settings.API_V1_PREFIX}/docs",
        redoc_url=None if is_prod else f"{settings.API_V1_PREFIX}/redoc",
        lifespan=lifespan,
    )

    # Configure CORS securely
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-CSRF-Token", "X-Request-ID"],
    )

    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if settings.ENVIRONMENT.lower() == "production" or settings.COOKIE_SECURE:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    # Register centralized exception handlers
    register_exception_handlers(app)

    # Mount API routers
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    # Top-level root endpoint
    @app.get("/", tags=["Root"])
    async def root_redirect():
        return {
            "application": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "docs": f"{settings.API_V1_PREFIX}/docs",
            "health": f"{settings.API_V1_PREFIX}/healthz",
        }

    return app


app = create_application()
