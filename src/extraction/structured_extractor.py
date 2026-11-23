"""
Structured extractor: Pydantic-validated LLM extraction for entity types.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.extraction.llm_orchestrator import get_orchestrator
from src.monitoring.logger import get_logger

logger = get_logger("extraction.structured_extractor")

STARTUP_EXTRACT_PROMPT = """Extract startup information from the following content.
Return JSON with keys: entity_name (string), employee_count (integer or null), description (string or null).
Only use facts directly from the content. Never invent data.

Content:
{content}"""

PRODUCT_EXTRACT_PROMPT = """Extract AI product information from the following content.
Return JSON with keys: entity_name (string), startup_name (string or null), 
pricing_model (one of FREE/FREEMIUM/PAID/ENTERPRISE/REVIEW), description (string or null).
Only assign pricing_model when there is explicit evidence. Use REVIEW if unsure.

Content:
{content}"""


async def extract_startup(html: str, source_url: str) -> Optional[Dict[str, Any]]:
    """Extract startup fields from HTML content using LLM."""
    orchestrator = get_orchestrator()
    return await orchestrator.extract(
        html, STARTUP_EXTRACT_PROMPT, source_url=source_url, record_type="STARTUP"
    )


async def extract_product(html: str, source_url: str) -> Optional[Dict[str, Any]]:
    """Extract product fields from HTML content using LLM."""
    orchestrator = get_orchestrator()
    return await orchestrator.extract(
        html, PRODUCT_EXTRACT_PROMPT, source_url=source_url, record_type="PRODUCT"
    )
