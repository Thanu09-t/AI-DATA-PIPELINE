"""
DeepSeek provider wrapper (OpenAI-compatible API).
"""
from __future__ import annotations

from typing import Optional
from src.config import settings
from src.monitoring.logger import get_logger

logger = get_logger("extraction.deepseek_provider")


async def call_deepseek(prompt: str, model: Optional[str] = None) -> Optional[str]:
    """Call DeepSeek API."""
    if not settings.deepseek_api_key:
        return None
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(
            api_key=settings.deepseek_api_key,
            base_url="https://api.deepseek.com",
        )
        response = await client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=model or settings.tertiary_llm_model,
            temperature=0.0,
        )
        return response.choices[0].message.content
    except Exception as exc:
        logger.error("DeepSeek call failed", extra={"error": str(exc)})
        return None
