"""
Async SQLAlchemy engine + session factory.
Supports PostgreSQL (primary) with SQLite fallback for local dev without Postgres.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from src.config import settings
from src.monitoring.logger import get_logger

logger = get_logger("database.connection")


def _get_engine_kwargs(url: Optional[str] = None) -> dict:
    """Return engine kwargs appropriate for the database URL."""
    if url is None:
        url = settings.database_url
    if "sqlite" in url:
        return {"connect_args": {"check_same_thread": False}}
    return {
        "pool_size": settings.db_pool_size,
        "max_overflow": settings.db_max_overflow,
        "pool_pre_ping": True,
        "pool_recycle": 1800,
    }


def create_engine() -> AsyncEngine:
    url = settings.database_url
    if os.environ.get("USE_SQLITE_FALLBACK", "1") == "1" or "sqlite" in url:
        url = "sqlite+aiosqlite:///data/ai_intelligence.db"
        logger.warning("Using SQLite fallback database")
    return create_async_engine(url, echo=False, **_get_engine_kwargs(url))


engine: AsyncEngine = create_engine()

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Context manager that yields an async DB session and handles commit/rollback."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Create all tables (dev convenience; use Alembic for production migrations)."""
    from src.database.models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created/verified")


async def dispose_engine() -> None:
    await engine.dispose()
    logger.info("Database engine disposed")
