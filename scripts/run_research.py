"""Run only the research paper pipeline."""
import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.pipelines.research_pipeline import run_research_pipeline
asyncio.run(run_research_pipeline())
