"""
Research pipeline: arXiv collection + GitHub enrichment.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from src.collectors.research_collector import ResearchCollector
from src.collectors.github_collector import GitHubCollector
from src.database.connection import get_session
from src.database.repository import PaperRepository
from src.monitoring.logger import get_logger
from src.monitoring.metrics import metrics
from src.processing.deduplicator import deduplicate_by_url, deduplicate_by_name
from src.processing.enrichment import enrich_paper
from src.processing.validators import validate_paper

logger = get_logger("pipelines.research")
UTC = timezone.utc


async def run_research_pipeline() -> Dict[str, Any]:
    pipeline_metrics = metrics.pipeline("research")
    start = datetime.now(UTC)

    logger.info("Starting research pipeline...")

    # Phase 1: Collect from arXiv
    async with ResearchCollector() as collector:
        raw_papers = await collector.collect()

    pipeline_metrics.records_discovered = len(raw_papers)
    logger.info(f"Collected {len(raw_papers)} raw papers")

    # Phase 2: Enrich (extract GitHub URLs from abstracts)
    enriched = [enrich_paper(p) for p in raw_papers]

    # Phase 3: Deduplicate by URL
    deduped, url_dups = deduplicate_by_url(enriched, url_field="paper_url")
    pipeline_metrics.duplicates_removed += url_dups
    logger.info(f"After URL dedup: {len(deduped)} papers (removed {url_dups})")

    # Phase 4: Validate
    valid: List[Dict[str, Any]] = []
    invalid = 0
    for paper in deduped:
        ok, errors = validate_paper(paper)
        if ok:
            paper["id"] = str(uuid.uuid4())
            valid.append(paper)
        else:
            invalid += 1
            logger.debug("Invalid paper", extra={"errors": errors, "title": paper.get("title", "")[:60]})

    pipeline_metrics.records_validated = len(valid)
    pipeline_metrics.records_rejected = invalid
    logger.info(f"Valid papers: {len(valid)}, rejected: {invalid}")

    # Phase 5: GitHub enrichment
    async with GitHubCollector() as github:
        valid = await github.enrich_papers(valid)

    enriched_with_github = sum(1 for p in valid if p.get("github_enriched"))
    logger.info(f"GitHub enriched: {enriched_with_github}/{len(valid)} papers")

    # Phase 6: Persist to database
    db_inserted = 0
    try:
        async with get_session() as session:
            repo = PaperRepository(session)
            # Convert datetime objects for JSON serialization
            db_records = []
            for p in valid:
                rec = dict(p)
                rec.pop("_pub_dt", None)
                rec.pop("_pub_verified", None)
                rec.pop("_pub_method", None)
                # Ensure authors is stored as JSON
                if isinstance(rec.get("authors"), list):
                    rec["authors"] = rec["authors"]
                db_records.append(rec)
            db_inserted = await repo.bulk_upsert(db_records)
            pipeline_metrics.db_writes = db_inserted
    except Exception as exc:
        logger.error("DB persistence failed", extra={"error": str(exc)})
        logger.info("Continuing without DB persistence: data available in memory")

    elapsed = (datetime.now(UTC) - start).total_seconds()
    result = {
        "status": "complete",
        "records_discovered": pipeline_metrics.records_discovered,
        "records_validated": len(valid),
        "records_rejected": invalid,
        "duplicates_removed": url_dups,
        "github_enriched": enriched_with_github,
        "db_inserted": db_inserted,
        "elapsed_seconds": elapsed,
        "papers": valid,
    }
    logger.info("Research pipeline complete", extra={k: v for k, v in result.items() if k != "papers"})
    return result
