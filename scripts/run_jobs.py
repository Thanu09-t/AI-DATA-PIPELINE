"""Run only the jobs pipeline."""
import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.pipelines.jobs_pipeline import run_jobs_pipeline
asyncio.run(run_jobs_pipeline())
