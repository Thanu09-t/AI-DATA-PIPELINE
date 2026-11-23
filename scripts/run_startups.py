"""Run only the startup pipeline."""
import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.pipelines.startup_pipeline import run_startup_pipeline
asyncio.run(run_startup_pipeline())
