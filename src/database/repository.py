"""
Database repository layer - CRUD operations for all entity types.
Uses upsert patterns for idempotency across distributed workers.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import select, func, text
try:
    from sqlalchemy.dialects.postgresql import insert as pg_insert
except ImportError:
    from sqlalchemy.dialects.sqlite import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import (
    EntityMapping, Job, LLMExtractionLog, NewsArticle,
    Product, ResearchPaper, Startup,
)
from src.monitoring.logger import get_logger

logger = get_logger("database.repository")


def _url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()


def _get_insert_stmt(model, session: AsyncSession):
    try:
        bind = session.get_bind()
        if bind and bind.dialect.name == "sqlite":
            return sqlite_insert(model)
    except Exception:
        pass
    return pg_insert(model)


# ─────────────────────────────────────────────────────────────────────────────
# STARTUP REPOSITORY
# ─────────────────────────────────────────────────────────────────────────────
class StartupRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert(self, data: Dict[str, Any]) -> Startup:
        """Insert or skip-on-conflict by source_url."""
        stmt = _get_insert_stmt(Startup, self.session).values(**data)
        stmt = stmt.on_conflict_do_nothing(index_elements=["source_url"])
        await self.session.execute(stmt)
        result = await self.session.execute(
            select(Startup).where(Startup.source_url == data["source_url"])
        )
        return result.scalar_one()

    async def bulk_upsert(self, records: List[Dict[str, Any]]) -> int:
        inserted = 0
        for rec in records:
            try:
                stmt = _get_insert_stmt(Startup, self.session).values(**rec)
                stmt = stmt.on_conflict_do_nothing(index_elements=["source_url"])
                result = await self.session.execute(stmt)
                if result.rowcount:
                    inserted += 1
            except Exception as exc:
                logger.warning("Startup upsert failed", extra={"error": str(exc), "url": rec.get("source_url")})
        return inserted

    async def count(self) -> int:
        result = await self.session.execute(select(func.count()).select_from(Startup))
        return result.scalar_one()

    async def all(self, limit: int = 10000) -> Sequence[Startup]:
        result = await self.session.execute(select(Startup).limit(limit))
        return result.scalars().all()


# ─────────────────────────────────────────────────────────────────────────────
# PRODUCT REPOSITORY
# ─────────────────────────────────────────────────────────────────────────────
class ProductRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def bulk_upsert(self, records: List[Dict[str, Any]]) -> int:
        inserted = 0
        for rec in records:
            try:
                data = dict(rec)
                if "product_name" in data and "entity_name" not in data:
                    data["entity_name"] = data["product_name"]
                if "entity_name" in data and "product_name" not in data:
                    data["product_name"] = data["entity_name"]
                if "company_name" in data and "startup_name" not in data:
                    data["startup_name"] = data["company_name"]
                if "startup_name" in data and "company_name" not in data:
                    data["company_name"] = data["startup_name"]
                stmt = _get_insert_stmt(Product, self.session).values(**data)
                stmt = stmt.on_conflict_do_nothing(index_elements=["source_url"])
                result = await self.session.execute(stmt)
                if result.rowcount:
                    inserted += 1
            except Exception as exc:
                logger.warning("Product upsert failed", extra={"error": str(exc)})
        return inserted

    async def count(self) -> int:
        result = await self.session.execute(select(func.count()).select_from(Product))
        return result.scalar_one()

    async def all(self, limit: int = 10000) -> Sequence[Product]:
        result = await self.session.execute(select(Product).limit(limit))
        return result.scalars().all()


# ─────────────────────────────────────────────────────────────────────────────
# RESEARCH PAPER REPOSITORY
# ─────────────────────────────────────────────────────────────────────────────
class PaperRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def bulk_upsert(self, records: List[Dict[str, Any]]) -> int:
        inserted = 0
        for rec in records:
            try:
                stmt = _get_insert_stmt(ResearchPaper, self.session).values(**rec)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["paper_url"],
                    set_={
                        "github_url": stmt.excluded.github_url,
                        "github_stars": stmt.excluded.github_stars,
                        "github_stars_collected_at": stmt.excluded.github_stars_collected_at,
                        "github_enriched": stmt.excluded.github_enriched,
                    },
                )
                result = await self.session.execute(stmt)
                if result.rowcount:
                    inserted += 1
            except Exception as exc:
                logger.warning("Paper upsert failed", extra={"error": str(exc)})
        return inserted

    async def unenriched(self, limit: int = 500) -> Sequence[ResearchPaper]:
        result = await self.session.execute(
            select(ResearchPaper)
            .where(ResearchPaper.github_enriched == False)
            .where(ResearchPaper.github_url.is_not(None))
            .limit(limit)
        )
        return result.scalars().all()

    async def count(self) -> int:
        result = await self.session.execute(select(func.count()).select_from(ResearchPaper))
        return result.scalar_one()

    async def all(self, limit: int = 10000) -> Sequence[ResearchPaper]:
        result = await self.session.execute(select(ResearchPaper).limit(limit))
        return result.scalars().all()


# ─────────────────────────────────────────────────────────────────────────────
# NEWS REPOSITORY
# ─────────────────────────────────────────────────────────────────────────────
class NewsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def bulk_upsert(self, records: List[Dict[str, Any]]) -> int:
        # Ensure url_hash is set
        for rec in records:
            if "url_hash" not in rec and "source_url" in rec:
                rec["url_hash"] = _url_hash(rec["source_url"])
        inserted = 0
        for rec in records:
            try:
                stmt = _get_insert_stmt(NewsArticle, self.session).values(**rec)
                stmt = stmt.on_conflict_do_nothing(index_elements=["url_hash"])
                result = await self.session.execute(stmt)
                if result.rowcount:
                    inserted += 1
            except Exception as exc:
                logger.warning("News upsert failed", extra={"error": str(exc)})
        return inserted

    async def fresh(self) -> Sequence[NewsArticle]:
        result = await self.session.execute(
            select(NewsArticle).where(NewsArticle.is_fresh == True)
        )
        return result.scalars().all()

    async def count(self) -> int:
        result = await self.session.execute(select(func.count()).select_from(NewsArticle))
        return result.scalar_one()

    async def all(self, limit: int = 10000) -> Sequence[NewsArticle]:
        result = await self.session.execute(select(NewsArticle).limit(limit))
        return result.scalars().all()


# ─────────────────────────────────────────────────────────────────────────────
# JOB REPOSITORY
# ─────────────────────────────────────────────────────────────────────────────
class JobRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def bulk_upsert(self, records: List[Dict[str, Any]]) -> int:
        for rec in records:
            if "url_hash" not in rec and "source_url" in rec:
                rec["url_hash"] = _url_hash(rec["source_url"])
        inserted = 0
        for rec in records:
            try:
                stmt = _get_insert_stmt(Job, self.session).values(**rec)
                stmt = stmt.on_conflict_do_nothing(index_elements=["url_hash"])
                result = await self.session.execute(stmt)
                if result.rowcount:
                    inserted += 1
            except Exception as exc:
                logger.warning("Job upsert failed", extra={"error": str(exc)})
        return inserted

    async def fresh(self) -> Sequence[Job]:
        result = await self.session.execute(
            select(Job).where(Job.is_fresh == True)
        )
        return result.scalars().all()

    async def count(self) -> int:
        result = await self.session.execute(select(func.count()).select_from(Job))
        return result.scalar_one()

    async def all(self, limit: int = 10000) -> Sequence[Job]:
        result = await self.session.execute(select(Job).limit(limit))
        return result.scalars().all()


# ─────────────────────────────────────────────────────────────────────────────
# ENTITY MAPPING REPOSITORY
# ─────────────────────────────────────────────────────────────────────────────
class EntityMappingRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def log(self, data: Dict[str, Any]) -> EntityMapping:
        mapping = EntityMapping(**data)
        self.session.add(mapping)
        return mapping

    async def bulk_log(self, records: List[Dict[str, Any]]) -> int:
        count = 0
        for rec in records:
            self.session.add(EntityMapping(**rec))
            count += 1
        return count

    async def count(self) -> int:
        result = await self.session.execute(select(func.count()).select_from(EntityMapping))
        return result.scalar_one()

    async def all(self, limit: int = 50000) -> Sequence[EntityMapping]:
        result = await self.session.execute(select(EntityMapping).limit(limit))
        return result.scalars().all()


# ─────────────────────────────────────────────────────────────────────────────
# LLM LOG REPOSITORY
# ─────────────────────────────────────────────────────────────────────────────
class LLMLogRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def log(self, data: Dict[str, Any]) -> LLMExtractionLog:
        entry = LLMExtractionLog(**data)
        self.session.add(entry)
        return entry
