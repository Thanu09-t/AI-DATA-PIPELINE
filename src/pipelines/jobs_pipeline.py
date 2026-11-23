"""
Jobs pipeline: multi-source AI job collection with strict 24-hour freshness.
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from src.collectors.job_collector import JobCollector
from src.database.connection import get_session
from src.database.repository import JobRepository
from src.monitoring.logger import get_logger
from src.monitoring.metrics import metrics
from src.processing.deduplicator import deduplicate_by_url
from src.processing.freshness_filter import apply_freshness_filter
from src.processing.validators import validate_job
from src.resolution.entity_resolver import get_resolver
from src.config import settings

logger = get_logger("pipelines.jobs")
UTC = timezone.utc


async def run_jobs_pipeline() -> Dict[str, Any]:
    pipeline_metrics = metrics.pipeline("jobs")
    start = datetime.now(UTC)
    resolver = get_resolver()

    logger.info("Starting jobs pipeline...")

    async with JobCollector() as collector:
        raw = await collector.collect()

    pipeline_metrics.records_discovered = len(raw)

    # Deduplicate by URL
    deduped, url_dups = deduplicate_by_url(raw, url_field="source_url")
    pipeline_metrics.duplicates_removed = url_dups

    # Apply freshness filter
    fresh, stale = apply_freshness_filter(
        deduped,
        date_fields=["published_at"],
        freshness_hours=settings.freshness_hours,
        now=start,
    )

    # Mark fresh records
    for rec in fresh:
        rec["is_fresh"] = True
        if rec.get("_pub_dt") and not isinstance(rec.get("published_at"), datetime):
            rec["published_at"] = rec["_pub_dt"]
        if rec.get("_pub_method"):
            rec["published_at_method"] = rec["_pub_method"]
        if rec.get("_pub_verified") is not None:
            rec["published_at_verified"] = rec["_pub_verified"]

    # Validate all + entity resolve company names
    valid: List[Dict[str, Any]] = []
    invalid = 0
    for rec in deduped:
        ok, errors = validate_job(rec)
        if not ok:
            invalid += 1
            continue

        company = rec.get("company")
        if company:
            canonical, method, score, review = resolver.resolve(
                company, source_url=rec.get("source_url"), record_type="JOB"
            )
            rec["canonical_company"] = canonical

        if "id" not in rec:
            rec["id"] = str(uuid.uuid4())

        # Clean up
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
            repo = JobRepository(session)
            db_records = []
            for r in valid:
                db_records.append({
                    "id": r.get("id"),
                    "title": r["title"],
                    "company": r.get("company"),
                    "canonical_company": r.get("canonical_company"),
                    "source_name": r["source_name"],
                    "source_url": r["source_url"],
                    "url_hash": r.get("url_hash", hashlib.sha256(r["source_url"].encode()).hexdigest()),
                    "published_at": r.get("published_at"),
                    "published_at_verified": r.get("published_at_verified", False),
                    "published_at_method": r.get("published_at_method"),
                    "discovered_at": r.get("discovered_at"),
                    "collected_at": r.get("collected_at", start),
                    "is_remote": r.get("is_remote"),
                    "role_family": r.get("role_family"),
                    "location": r.get("location"),
                    "is_fresh": r.get("is_fresh", False),
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
        "fresh_jobs": fresh_count,
        "stale_jobs": len(valid) - fresh_count,
        "records_rejected": invalid,
        "duplicates_removed": url_dups,
        "db_inserted": db_inserted,
        "elapsed_seconds": elapsed,
        "jobs": valid,
    }
    logger.info("Jobs pipeline complete", extra={k: v for k, v in result.items() if k != "jobs"})
    return result
