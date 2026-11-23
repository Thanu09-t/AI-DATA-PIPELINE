"""
Run all pipelines end-to-end from the command line.
Usage: python scripts/run_all.py
"""
import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import settings
from src.monitoring.logger import setup_root_logger
from src.pipelines.orchestrator import run_all_pipelines

logger = setup_root_logger(level=settings.log_level, log_dir=settings.logs_dir)


async def main():
    print("=" * 70)
    print("  AI Intelligence Ingestion Platform: Full Pipeline Run")
    print("=" * 70)
    
    summary = await run_all_pipelines()

    print("\n" + "=" * 70)
    print("  EXECUTION SUMMARY")
    print("=" * 70)
    print(f"  Status:                   {summary.get('status')}")
    print(f"  Total elapsed:            {summary.get('elapsed_seconds', 0):.1f}s")
    print(f"  Startups discovered:      {summary.get('startups_discovered', 0)}")
    print(f"  Startups validated:       {summary.get('startups_validated', 0)}")
    print(f"  Products discovered:      {summary.get('products_discovered', 0)}")
    print(f"  Products validated:       {summary.get('products_validated', 0)}")
    print(f"  Papers discovered:        {summary.get('papers_discovered', 0)}")
    print(f"  Papers validated:         {summary.get('papers_validated', 0)}")
    print(f"  GitHub enriched:          {summary.get('papers_github_enriched', 0)}")
    print(f"  Fresh news articles:      {summary.get('fresh_news', 0)}")
    print(f"  Fresh jobs:               {summary.get('fresh_jobs', 0)}")
    print(f"  Entity mappings logged:   {summary.get('entity_mappings', 0)}")
    print("=" * 70)
    
    exports = summary.get("exports", {})
    print("\n  EXPORT LOCATIONS:")
    for k, v in exports.items():
        if v and k != "google_sheets_url":
            print(f"    {k}: {v}")
    if exports.get("google_sheets_url"):
        print(f"  Google Sheets: {exports['google_sheets_url']}")
    else:
        print("  Google Sheets: Not configured (see .env.example)")
    print("=" * 70)
    
    return summary


if __name__ == "__main__":
    asyncio.run(main())
