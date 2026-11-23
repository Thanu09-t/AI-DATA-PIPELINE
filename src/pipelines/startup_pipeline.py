"""
Startup pipeline: multi-source startup collection.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from src.collectors.startup_collector import StartupCollector
from src.database.connection import get_session
from src.database.repository import StartupRepository
from src.monitoring.logger import get_logger
from src.monitoring.metrics import metrics
from src.processing.deduplicator import deduplicate_pipeline
from src.processing.enrichment import enrich_startup
from src.processing.validators import validate_startup
from src.resolution.entity_resolver import get_resolver

logger = get_logger("pipelines.startup")
UTC = timezone.utc


async def run_startup_pipeline() -> Dict[str, Any]:
    pipeline_metrics = metrics.pipeline("startup")
    start = datetime.now(UTC)
    resolver = get_resolver()

    logger.info("Starting startup pipeline...")

    async with StartupCollector() as collector:
        raw = await collector.collect()

    pipeline_metrics.records_discovered = len(raw)

    # Enrich
    enriched = [enrich_startup(r) for r in raw]

    # Deduplicate
    deduped, dedup_stats = deduplicate_pipeline(enriched, url_field="source_url", name_field="entity_name")
    pipeline_metrics.duplicates_removed = dedup_stats["total_removed"]

    # Validate + entity resolution
    valid: List[Dict[str, Any]] = []
    invalid = 0
    for rec in deduped:
        ok, errors = validate_startup(rec)
        if not ok:
            invalid += 1
            continue
        # Entity resolution
        raw_name = rec["entity_name"]
        canonical, method, score, review = resolver.resolve(
            raw_name, source_url=rec.get("source_url"), record_type="STARTUP"
        )
        rec["canonical_name"] = canonical
        rec["id"] = str(uuid.uuid4())
        valid.append(rec)

    pipeline_metrics.records_validated = len(valid)
    pipeline_metrics.records_rejected = invalid

    # Persist
    db_inserted = 0
    try:
        async with get_session() as session:
            repo = StartupRepository(session)
            db_records = []
            for r in valid:
                rec = {
                    "id": r.get("id"),
                    "entity_name": r["entity_name"],
                    "canonical_name": r.get("canonical_name"),
                    "source_name": r["source_name"],
                    "source_url": r["source_url"],
                    "employee_count": r.get("employee_count"),
                    "description": r.get("description"),
                    "extra_data": r.get("extra_data"),
                    "collected_at": r.get("collected_at"),
                }
                db_records.append(rec)
            db_inserted = await repo.bulk_upsert(db_records)
    except Exception as exc:
        logger.error("DB write failed", extra={"error": str(exc)})

    elapsed = (datetime.now(UTC) - start).total_seconds()
    result = {
        "status": "complete",
        "records_discovered": pipeline_metrics.records_discovered,
        "records_validated": len(valid),
        "records_rejected": invalid,
        "duplicates_removed": pipeline_metrics.duplicates_removed,
        "db_inserted": db_inserted,
        "elapsed_seconds": elapsed,
        "startups": valid,
    }
    logger.info("Startup pipeline complete", extra={k: v for k, v in result.items() if k != "startups"})
    return result
