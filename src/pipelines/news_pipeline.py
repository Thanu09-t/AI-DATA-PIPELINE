"""
News pipeline: multi-source news collection with strict 24-hour freshness.
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from src.collectors.news_collector import NewsCollector
from src.database.connection import get_session
from src.database.repository import NewsRepository
from src.monitoring.logger import get_logger
from src.monitoring.metrics import metrics
from src.processing.deduplicator import deduplicate_by_url
from src.processing.freshness_filter import apply_freshness_filter
from src.processing.validators import validate_news
from src.config import settings

logger = get_logger("pipelines.news")
UTC = timezone.utc


async def run_news_pipeline() -> Dict[str, Any]:
    pipeline_metrics = metrics.pipeline("news")
    start = datetime.now(UTC)

    logger.info("Starting news pipeline...")

    async with NewsCollector() as collector:
        raw = await collector.collect()

    pipeline_metrics.records_discovered = len(raw)

    # Deduplicate by URL
    deduped, url_dups = deduplicate_by_url(raw, url_field="source_url")
    pipeline_metrics.duplicates_removed = url_dups

    # Apply strict 24-hour freshness filter
    fresh, stale = apply_freshness_filter(
        deduped,
        date_fields=["published_at"],
        freshness_hours=settings.freshness_hours,
        now=start,
    )

    # Update is_fresh flag
    for rec in fresh:
        rec["is_fresh"] = True
        rec["freshness_checked_at"] = start
        # Apply pub date annotations from freshness filter
        if rec.get("_pub_dt"):
            if not isinstance(rec.get("published_at"), datetime):
                rec["published_at"] = rec["_pub_dt"]
        if rec.get("_pub_method"):
            rec["published_at_method"] = rec["_pub_method"]
        if rec.get("_pub_verified") is not None:
            rec["published_at_verified"] = rec["_pub_verified"]

    # Validate
    valid: List[Dict[str, Any]] = []
    invalid = 0
    for rec in deduped:  # Validate all, not just fresh
        ok, errors = validate_news(rec)
        if not ok:
            invalid += 1
            continue
        if "id" not in rec:
            rec["id"] = str(uuid.uuid4())
        # Clean up helper fields
        rec.pop("_pub_dt", None)
        rec.pop("_pub_verified", None)
        rec.pop("_pub_method", None)
        valid.append(rec)

    pipeline_metrics.records_validated = len(valid)
    pipeline_metrics.records_rejected = invalid

    fresh_count = sum(1 for r in valid if r.get("is_fresh"))

    # Persist
    db_inserted = 0
    try:
        async with get_session() as session:
            repo = NewsRepository(session)
            db_records = []
            for r in valid:
                db_records.append({
                    "id": r.get("id"),
                    "title": r["title"],
                    "full_text": r.get("full_text"),
                    "source_name": r["source_name"],
                    "source_url": r["source_url"],
                    "url_hash": r.get("url_hash", hashlib.sha256(r["source_url"].encode()).hexdigest()),
                    "published_at": r.get("published_at"),
                    "published_at_verified": r.get("published_at_verified", False),
                    "published_at_method": r.get("published_at_method"),
                    "discovered_at": r.get("discovered_at"),
                    "collected_at": r.get("collected_at", start),
                    "is_fresh": r.get("is_fresh", False),
                    "freshness_checked_at": r.get("freshness_checked_at"),
                    "extra_data": r.get("extra_data"),
                })
            db_inserted = await repo.bulk_upsert(db_records)
    except Exception as exc:
        logger.error("DB write failed", extra={"error": str(exc)})

    elapsed = (datetime.now(UTC) - start).total_seconds()
    result = {
        "status": "complete",
        "records_discovered": pipeline_metrics.records_discovered,
        "records_validated": len(valid),
        "fresh_articles": fresh_count,
        "stale_articles": len(valid) - fresh_count,
        "records_rejected": invalid,
        "duplicates_removed": url_dups,
        "db_inserted": db_inserted,
        "elapsed_seconds": elapsed,
        "news": valid,
    }
    logger.info("News pipeline complete", extra={k: v for k, v in result.items() if k != "news"})
    return result
