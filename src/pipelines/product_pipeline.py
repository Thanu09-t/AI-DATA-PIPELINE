"""
Product pipeline: Hugging Face and GitHub product collection.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from src.collectors.product_collector import ProductCollector
from src.database.connection import get_session
from src.database.repository import ProductRepository
from src.monitoring.logger import get_logger
from src.monitoring.metrics import metrics
from src.processing.deduplicator import deduplicate_pipeline
from src.processing.enrichment import enrich_product
from src.processing.validators import validate_product
from src.resolution.entity_resolver import get_resolver

logger = get_logger("pipelines.product")
UTC = timezone.utc


async def run_product_pipeline() -> Dict[str, Any]:
    pipeline_metrics = metrics.pipeline("product")
    start = datetime.now(UTC)
    resolver = get_resolver()

    logger.info("Starting product pipeline...")

    async with ProductCollector() as collector:
        raw = await collector.collect()

    pipeline_metrics.records_discovered = len(raw)

    enriched = [enrich_product(r) for r in raw]
    deduped, dedup_stats = deduplicate_pipeline(enriched, url_field="source_url", name_field="entity_name")
    pipeline_metrics.duplicates_removed = dedup_stats["total_removed"]

    valid: List[Dict[str, Any]] = []
    invalid = 0
    for rec in deduped:
        ok, errors = validate_product(rec)
        if not ok:
            invalid += 1
            continue
        # Ensure canonical product_name and company_name
        p_name = rec.get("product_name") or rec.get("entity_name") or ""
        c_name = rec.get("company_name") or rec.get("startup_name") or "Unknown"
        rec["product_name"] = p_name
        rec["entity_name"] = p_name

        # Resolve company/startup name
        if c_name and c_name != "Unknown":
            canonical, method, score, review = resolver.resolve(
                c_name, source_url=rec.get("source_url"), record_type="PRODUCT"
            )
            rec["startup_name"] = canonical
            rec["company_name"] = canonical
        else:
            rec["startup_name"] = "Unknown"
            rec["company_name"] = "Unknown"

        rec["id"] = str(uuid.uuid4())
        valid.append(rec)

    pipeline_metrics.records_validated = len(valid)
    pipeline_metrics.records_rejected = invalid

    # Persist
    db_inserted = 0
    try:
        async with get_session() as session:
            repo = ProductRepository(session)
            db_records = []
            for r in valid:
                db_records.append({
                    "id": r.get("id"),
                    "entity_name": r["entity_name"],
                    "product_name": r.get("product_name", r["entity_name"]),
                    "startup_name": r.get("startup_name"),
                    "company_name": r.get("company_name", r.get("startup_name")),
                    "pricing_model": r.get("pricing_model"),
                    "source_name": r["source_name"],
                    "source_url": r["source_url"],
                    "description": r.get("description"),
                    "extra_data": r.get("extra_data"),
                    "collected_at": r.get("collected_at"),
                })
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
        "products": valid,
    }
    logger.info("Product pipeline complete", extra={k: v for k, v in result.items() if k != "products"})
    return result
