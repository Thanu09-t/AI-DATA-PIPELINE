"""Run only the news pipeline."""
import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.pipelines.news_pipeline import run_news_pipeline
asyncio.run(run_news_pipeline())
