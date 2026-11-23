"""
Gemini Flash provider wrapper.
"""
from __future__ import annotations

from typing import Optional
from src.config import settings
from src.monitoring.logger import get_logger

logger = get_logger("extraction.gemini_provider")


async def call_gemini(prompt: str, model: Optional[str] = None) -> Optional[str]:
    """Call Gemini Flash API directly."""
    if not settings.gemini_api_key:
        return None
    try:
        import google.generativeai as genai
        import asyncio
        genai.configure(api_key=settings.gemini_api_key)
        m = genai.GenerativeModel(model or settings.primary_llm_model)
        response = await asyncio.to_thread(m.generate_content, prompt)
        return response.text if response.text else None
    except Exception as exc:
        logger.error("Gemini call failed", extra={"error": str(exc)})
        return None
