import asyncio
import logging
from typing import AsyncGenerator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from app.core.config import settings

logger = logging.getLogger("cargopulse.database")

# Create Async SQLAlchemy Engine with connection pool parameters
async_engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG and False,  # Keep False to prevent sensitive payload dumping
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=settings.DB_POOL_RECYCLE,
    pool_pre_ping=True,  # Test connection viability before handing to caller
    connect_args={"timeout": 10} if settings.ENVIRONMENT.lower() == "production" else {"timeout": 10, "ssl": False},
)

# Create Async Session Factory
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency yielding an isolated AsyncSession within a transactional context.
    Rolls back automatically on unhandled exception.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def check_db_health() -> dict:
    """
    Actively probes PostgreSQL database connectivity and response time.
    """
    # Quick non-blocking socket check first
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(settings.POSTGRES_SERVER, settings.POSTGRES_PORT),
            timeout=1.5
        )
        writer.close()
        await writer.wait_closed()
    except Exception as exc:
        return {
            "status": "unhealthy",
            "database": "postgresql",
            "connected": False,
            "error": f"PostgreSQL port closed at {settings.POSTGRES_SERVER}:{settings.POSTGRES_PORT}",
        }

    async def _probe():
        async with async_engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            scalar = result.scalar()
            if scalar == 1:
                return {"status": "healthy", "database": "postgresql", "connected": True}
        return {"status": "unhealthy", "database": "postgresql", "connected": False}

    try:
        return await asyncio.wait_for(_probe(), timeout=2.0)
    except Exception as exc:
        logger.warning(f"Database health check query failed: {exc}")
        return {"status": "unhealthy", "database": "postgresql", "connected": False, "error": str(exc)}
