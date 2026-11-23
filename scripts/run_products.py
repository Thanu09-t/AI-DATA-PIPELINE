"""Run only the product pipeline."""
import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.pipelines.product_pipeline import run_product_pipeline
asyncio.run(run_product_pipeline())
