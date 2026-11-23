"""
Master pipeline orchestrator: runs all pipelines, manages entity resolution,
exports results, and produces the final summary report.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.config import settings
from src.database.connection import init_db
from src.exports.csv_exporter import export_all_csv
from src.exports.excel_exporter import export_excel
from src.exports.json_exporter import export_all_json
from src.exports.google_sheets_exporter import export_to_google_sheets
from src.monitoring.logger import get_logger
from src.monitoring.metrics import metrics
from src.pipelines.startup_pipeline import run_startup_pipeline
from src.pipelines.product_pipeline import run_product_pipeline
from src.pipelines.research_pipeline import run_research_pipeline
from src.pipelines.news_pipeline import run_news_pipeline
from src.pipelines.jobs_pipeline import run_jobs_pipeline
from src.resolution.entity_resolver import get_resolver
from src.resolution.mapping_logger import export_mapping_log

logger = get_logger("pipelines.orchestrator")
UTC = timezone.utc


async def run_all_pipelines(
    pipelines: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Run all (or selected) pipelines and produce exports.
    Returns a comprehensive summary report.
    """
    if pipelines is None:
        pipelines = ["startups", "products", "research", "news", "jobs"]

    start = datetime.now(UTC)
    logger.info("=" * 60)
    logger.info("AI Intelligence Ingestion Platform: Full Run")
    logger.info(f"Pipelines: {pipelines}")
    logger.info(f"Start time: {start.isoformat()}")
    logger.info("=" * 60)

    # Initialize database
    try:
        await init_db()
    except Exception as exc:
        logger.warning(f"DB init failed (continuing): {exc}")

    results: Dict[str, Any] = {}

    # Run pipelines concurrently where safe
    if "startups" in pipelines and "products" in pipelines and "research" in pipelines:
        # Run startups, products, research concurrently
        startup_task = asyncio.create_task(run_startup_pipeline())
        product_task = asyncio.create_task(run_product_pipeline())
        research_task = asyncio.create_task(run_research_pipeline())

        startup_result, product_result, research_result = await asyncio.gather(
            startup_task, product_task, research_task, return_exceptions=True
        )
        results["startups"] = startup_result if not isinstance(startup_result, Exception) else {"status": "error", "error": str(startup_result)}
        results["products"] = product_result if not isinstance(product_result, Exception) else {"status": "error", "error": str(product_result)}
        results["research"] = research_result if not isinstance(research_result, Exception) else {"status": "error", "error": str(research_result)}
    else:
        if "startups" in pipelines:
            results["startups"] = await run_startup_pipeline()
        if "products" in pipelines:
            results["products"] = await run_product_pipeline()
        if "research" in pipelines:
            results["research"] = await run_research_pipeline()

    # News and jobs (can run concurrently)
    if "news" in pipelines and "jobs" in pipelines:
        news_result, jobs_result = await asyncio.gather(
            run_news_pipeline(), run_jobs_pipeline(), return_exceptions=True
        )
        results["news"] = news_result if not isinstance(news_result, Exception) else {"status": "error", "error": str(news_result)}
        results["jobs"] = jobs_result if not isinstance(jobs_result, Exception) else {"status": "error", "error": str(jobs_result)}
    else:
        if "news" in pipelines:
            results["news"] = await run_news_pipeline()
        if "jobs" in pipelines:
            results["jobs"] = await run_jobs_pipeline()

    # Entity resolution mapping log
    resolver = get_resolver()
    mapping_log = resolver.get_mapping_log()
    resolver_stats = resolver.stats()

    # Export mapping log
    mapping_log_path = settings.exports_dir / "entity_mapping_log.csv"
    export_mapping_log(mapping_log, mapping_log_path)

    # Export all data
    logger.info("Exporting data...")
    export_data = _prepare_export_data(results)

    # CSV exports
    csv_paths = export_all_csv(export_data, settings.exports_dir)

    # JSON exports
    json_paths = export_all_json(export_data, settings.exports_dir)

    # Excel export
    excel_path = settings.exports_dir / "ai_intelligence_output.xlsx"
    export_excel(export_data, excel_path, mapping_log)

    # Google Sheets (if configured)
    sheets_url = None
    if settings.google_sheets_credentials:
        try:
            sheets_url = await asyncio.to_thread(
                export_to_google_sheets, export_data, mapping_log, settings
            )
        except Exception as exc:
            logger.error("Google Sheets export failed", extra={"error": str(exc)})

    elapsed = (datetime.now(UTC) - start).total_seconds()

    # Build summary
    summary = _build_summary(results, mapping_log, resolver_stats, elapsed)
    summary["exports"] = {
        "csv": csv_paths,
        "json": json_paths,
        "excel": str(excel_path),
        "entity_mapping_log": str(mapping_log_path),
        "google_sheets_url": sheets_url,
    }

    logger.info("=" * 60)
    logger.info("PIPELINE COMPLETE")
    logger.info(f"Total elapsed: {elapsed:.1f}s")
    logger.info(f"Startups validated: {summary.get('startups_validated', 0)}")
    logger.info(f"Products validated: {summary.get('products_validated', 0)}")
    logger.info(f"Papers validated: {summary.get('papers_validated', 0)}")
    logger.info(f"Fresh news: {summary.get('fresh_news', 0)}")
    logger.info(f"Fresh jobs: {summary.get('fresh_jobs', 0)}")
    logger.info(f"Entity mappings: {len(mapping_log)}")
    logger.info("=" * 60)

    return summary


def _prepare_export_data(results: Dict[str, Any]) -> Dict[str, List[Dict]]:
    """Extract record lists from pipeline results for export."""
    return {
        "startups": results.get("startups", {}).get("startups", []) if isinstance(results.get("startups"), dict) else [],
        "products": results.get("products", {}).get("products", []) if isinstance(results.get("products"), dict) else [],
        "research_papers": results.get("research", {}).get("papers", []) if isinstance(results.get("research"), dict) else [],
        "news": results.get("news", {}).get("news", []) if isinstance(results.get("news"), dict) else [],
        "jobs": results.get("jobs", {}).get("jobs", []) if isinstance(results.get("jobs"), dict) else [],
    }


def _build_summary(
    results: Dict[str, Any],
    mapping_log: List[Dict],
    resolver_stats: Dict[str, int],
    elapsed: float,
) -> Dict[str, Any]:
    """Build the final summary report."""
    startup_r = results.get("startups", {}) if isinstance(results.get("startups"), dict) else {}
    product_r = results.get("products", {}) if isinstance(results.get("products"), dict) else {}
    research_r = results.get("research", {}) if isinstance(results.get("research"), dict) else {}
    news_r = results.get("news", {}) if isinstance(results.get("news"), dict) else {}
    jobs_r = results.get("jobs", {}) if isinstance(results.get("jobs"), dict) else {}

    return {
        "status": "complete",
        "elapsed_seconds": round(elapsed, 2),
        # Startups
        "startups_discovered": startup_r.get("records_discovered", 0),
        "startups_validated": startup_r.get("records_validated", 0),
        "startups_rejected": startup_r.get("records_rejected", 0),
        "startups_duplicates": startup_r.get("duplicates_removed", 0),
        # Products
        "products_discovered": product_r.get("records_discovered", 0),
        "products_validated": product_r.get("records_validated", 0),
        "products_rejected": product_r.get("records_rejected", 0),
        "products_duplicates": product_r.get("duplicates_removed", 0),
        # Research
        "papers_discovered": research_r.get("records_discovered", 0),
        "papers_validated": research_r.get("records_validated", 0),
        "papers_rejected": research_r.get("records_rejected", 0),
        "papers_github_enriched": research_r.get("github_enriched", 0),
        # News
        "news_discovered": news_r.get("records_discovered", 0),
        "news_validated": news_r.get("records_validated", 0),
        "fresh_news": news_r.get("fresh_articles", 0),
        # Jobs
        "jobs_discovered": jobs_r.get("records_discovered", 0),
        "jobs_validated": jobs_r.get("records_validated", 0),
        "fresh_jobs": jobs_r.get("fresh_jobs", 0),
        # Entity resolution
        "entity_mappings": len(mapping_log),
        "entity_resolution_stats": resolver_stats,
        # Metrics
        "llm_metrics": metrics.pipeline("llm").to_dict(),
        "pipeline_statuses": {k: v.get("status") if isinstance(v, dict) else "error" for k, v in results.items()},
    }
