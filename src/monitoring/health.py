"""
Health-check utilities for FastAPI /health endpoint.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict

async def check_redis(redis_url: str) -> Dict[str, Any]:
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(redis_url, socket_connect_timeout=2)
        await r.ping()
        await r.aclose()
        return {"status": "ok"}
    except ImportError:
        return {"status": "skipped", "detail": "redis package not installed"}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


async def check_database(db_url: str) -> Dict[str, Any]:
    try:
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy import text

        engine = create_async_engine(db_url, pool_pre_ping=True, pool_size=1)
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        await engine.dispose()
        return {"status": "ok"}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


async def build_health_report(settings: Any) -> Dict[str, Any]:
    redis_check, db_check = await asyncio.gather(
        check_redis(settings.redis_url),
        check_database(settings.database_url),
        return_exceptions=False,
    )
    overall = "ok" if redis_check["status"] == "ok" and db_check["status"] == "ok" else "degraded"
    return {
        "status": overall,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": {
            "redis": redis_check,
            "database": db_check,
        },
    }
