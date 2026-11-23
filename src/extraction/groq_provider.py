"""
Groq (Llama 3) provider wrapper.
"""
from __future__ import annotations

from typing import Optional
from src.config import settings
from src.monitoring.logger import get_logger

logger = get_logger("extraction.groq_provider")


async def call_groq(prompt: str, model: Optional[str] = None) -> Optional[str]:
    """Call Groq Llama 3 API."""
    if not settings.groq_api_key:
        return None
    try:
        from groq import AsyncGroq
        client = AsyncGroq(api_key=settings.groq_api_key)
        response = await client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=model or settings.secondary_llm_model,
            temperature=0.0,
        )
        return response.choices[0].message.content
    except Exception as exc:
        logger.error("Groq call failed", extra={"error": str(exc)})
        return None
