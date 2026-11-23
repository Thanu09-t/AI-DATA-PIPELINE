"""
LLM Orchestrator: multi-provider fallback chain.
PRIMARY: Gemini Flash
SECONDARY: Groq (Llama 3)
TERTIARY: DeepSeek

Implements:
- Exponential backoff with jitter for 429
- Payload reduction for 413 / context overflow
- Circuit breaker per provider
- Detailed extraction logging
"""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Type

from pydantic import BaseModel

from src.config import settings
from src.extraction.chunking import SemanticChunker
from src.monitoring.logger import get_logger
from src.monitoring.metrics import metrics

logger = get_logger("extraction.llm_orchestrator")
UTC = timezone.utc


class ProviderStatus(str, Enum):
    OK = "ok"
    RATE_LIMITED = "rate_limited"
    CIRCUIT_OPEN = "circuit_open"
    UNAVAILABLE = "unavailable"


@dataclass
class ProviderState:
    name: str
    model: str
    failures: int = 0
    last_failure: Optional[float] = None
    status: ProviderStatus = ProviderStatus.OK
    circuit_open_until: Optional[float] = None
    circuit_threshold: int = 5
    circuit_reset_seconds: float = 120.0

    def record_failure(self) -> None:
        self.failures += 1
        self.last_failure = time.monotonic()
        if self.failures >= self.circuit_threshold:
            self.circuit_open_until = time.monotonic() + self.circuit_reset_seconds
            self.status = ProviderStatus.CIRCUIT_OPEN
            logger.warning(
                f"Circuit breaker OPEN for provider {self.name}",
                extra={"failures": self.failures},
            )

    def record_success(self) -> None:
        self.failures = 0
        self.last_failure = None
        self.status = ProviderStatus.OK
        self.circuit_open_until = None

    def is_available(self) -> bool:
        if self.status == ProviderStatus.CIRCUIT_OPEN:
            if self.circuit_open_until and time.monotonic() > self.circuit_open_until:
                # Try half-open
                self.status = ProviderStatus.OK
                self.failures = 0
                logger.info(f"Circuit breaker HALF-OPEN for {self.name}")
                return True
            return False
        return True


class LLMOrchestrator:
    """
    Provider-independent LLM extraction orchestrator.
    Implements primary → secondary → tertiary fallback chain.
    """

    SYSTEM_PROMPT = """You are a precise data extraction assistant.
Extract ONLY facts directly supported by the supplied source content.
Return null for missing values.
Never infer a date, employee count, repository, GitHub star count, company name, or pricing model without evidence.
Return valid JSON matching the requested schema exactly."""

    def __init__(self):
        self._chunker = SemanticChunker(max_tokens=settings.chunk_token_limit)
        self._pipeline_metrics = metrics.pipeline("llm")
        self._providers: List[ProviderState] = [
            ProviderState(
                name=settings.primary_llm_provider,
                model=settings.primary_llm_model,
            ),
            ProviderState(
                name=settings.secondary_llm_provider,
                model=settings.secondary_llm_model,
            ),
            ProviderState(
                name=settings.tertiary_llm_provider,
                model=settings.tertiary_llm_model,
            ),
        ]

    def _get_available_providers(self) -> List[ProviderState]:
        return [p for p in self._providers if p.is_available()]

    async def _call_gemini(self, provider: ProviderState, prompt: str) -> Optional[str]:
        """Call Google Gemini Flash API."""
        if not settings.gemini_api_key:
            return None
        try:
            import google.generativeai as genai
            genai.configure(api_key=settings.gemini_api_key)
            model = genai.GenerativeModel(provider.model)
            response = await asyncio.to_thread(
                model.generate_content,
                [self.SYSTEM_PROMPT, prompt],
                generation_config=genai.types.GenerationConfig(
                    temperature=0.0,
                    max_output_tokens=4096,
                ),
            )
            return response.text if response.text else None
        except Exception as exc:
            err_str = str(exc).lower()
            if "429" in err_str or "quota" in err_str or "rate" in err_str:
                raise RateLimitError(f"Gemini 429: {exc}")
            if "413" in err_str or "too large" in err_str:
                raise PayloadTooLargeError(f"Gemini 413: {exc}")
            raise

    async def _call_groq(self, provider: ProviderState, prompt: str) -> Optional[str]:
        """Call Groq API (Llama 3)."""
        if not settings.groq_api_key:
            return None
        try:
            from groq import AsyncGroq
            client = AsyncGroq(api_key=settings.groq_api_key)
            response = await client.chat.completions.create(
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                model=provider.model,
                temperature=0.0,
                max_tokens=4096,
            )
            return response.choices[0].message.content
        except Exception as exc:
            err_str = str(exc).lower()
            if "429" in err_str or "rate" in err_str:
                raise RateLimitError(f"Groq 429: {exc}")
            if "413" in err_str or "too large" in err_str:
                raise PayloadTooLargeError(f"Groq 413: {exc}")
            raise

    async def _call_deepseek(self, provider: ProviderState, prompt: str) -> Optional[str]:
        """Call DeepSeek API (OpenAI-compatible)."""
        if not settings.deepseek_api_key:
            return None
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(
                api_key=settings.deepseek_api_key,
                base_url="https://api.deepseek.com",
            )
            response = await client.chat.completions.create(
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                model=provider.model,
                temperature=0.0,
                max_tokens=4096,
            )
            return response.choices[0].message.content
        except Exception as exc:
            err_str = str(exc).lower()
            if "429" in err_str or "rate" in err_str:
                raise RateLimitError(f"DeepSeek 429: {exc}")
            if "413" in err_str or "too large" in err_str:
                raise PayloadTooLargeError(f"DeepSeek 413: {exc}")
            raise

    async def _call_provider(self, provider: ProviderState, prompt: str) -> Optional[str]:
        """Dispatch to the appropriate provider API."""
        name = provider.name.lower()
        if name == "gemini":
            return await self._call_gemini(provider, prompt)
        if name == "groq":
            return await self._call_groq(provider, prompt)
        if name == "deepseek":
            return await self._call_deepseek(provider, prompt)
        raise ValueError(f"Unknown provider: {name}")

    def _extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract JSON object from LLM response (handles markdown code blocks)."""
        if not text:
            return None
        import re
        # Try direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        # Try extracting JSON from markdown code block
        m = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass
        # Try finding the first { ... } block
        m = re.search(r"\{[\s\S]+\}", text)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
        return None

    async def extract(
        self,
        content: str,
        prompt_template: str,
        source_url: Optional[str] = None,
        record_type: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Extract structured data from content using the LLM fallback chain.
        Handles 429 (rate limit) and 413/overflow (chunking).
        Returns extracted dict or None.
        """
        providers = self._get_available_providers()
        if not providers:
            logger.error("All LLM providers unavailable: circuit breakers open")
            return None

        # Check if content needs chunking
        chunks = self._chunker.chunk(content)
        if len(chunks) > 1:
            logger.info(
                f"Content chunked: {len(chunks)} chunks",
                extra={"source_url": source_url},
            )
            return await self._extract_chunked(chunks, prompt_template, source_url, record_type)

        prompt = prompt_template.replace("{content}", content)

        for provider in providers:
            self._pipeline_metrics.llm_calls += 1
            attempt = 0
            base_delay = 1.0
            max_delay = 60.0

            while attempt <= settings.max_retries:
                try:
                    raw = await self._call_provider(provider, prompt)
                    if raw:
                        result = self._extract_json(raw)
                        if result:
                            provider.record_success()
                            return result
                        logger.warning(
                            "LLM returned non-JSON response",
                            extra={"provider": provider.name, "preview": raw[:200]},
                        )
                    provider.record_failure()
                    break

                except RateLimitError:
                    self._pipeline_metrics.rate_limit_events += 1
                    import random
                    wait = min(base_delay * (2 ** attempt) + random.uniform(0, 2), max_delay)
                    logger.warning(
                        f"Rate limit on {provider.name}, waiting {wait:.1f}s",
                        extra={"attempt": attempt},
                    )
                    await asyncio.sleep(wait)
                    attempt += 1
                    self._pipeline_metrics.retry_attempts += 1

                except PayloadTooLargeError:
                    logger.warning(
                        f"Payload too large for {provider.name}: reducing chunk size"
                    )
                    # Reduce chunk size and retry with smaller content
                    reduced = content[:len(content) // 2]
                    prompt = prompt_template.replace("{content}", reduced)
                    attempt += 1

                except Exception as exc:
                    logger.error(
                        f"LLM provider {provider.name} error",
                        extra={"error": str(exc), "attempt": attempt},
                    )
                    provider.record_failure()
                    self._pipeline_metrics.llm_failures += 1
                    break

            # Try next provider
            self._pipeline_metrics.provider_switches += 1
            logger.info(f"Switching LLM provider from {provider.name}")

        logger.error("All LLM providers exhausted")
        return None

    async def _extract_chunked(
        self,
        chunks: List[str],
        prompt_template: str,
        source_url: Optional[str],
        record_type: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        """Extract from multiple chunks and merge results."""
        results: List[Dict[str, Any]] = []
        for i, chunk in enumerate(chunks):
            prompt = prompt_template.replace("{content}", chunk)
            result = await self.extract(chunk, prompt_template, source_url, record_type)
            if result:
                results.append(result)

        if not results:
            return None
        if len(results) == 1:
            return results[0]

        # Merge: use first non-null value for each key
        merged: Dict[str, Any] = {}
        for result in results:
            for k, v in result.items():
                if k not in merged or merged[k] is None:
                    merged[k] = v
        return merged


class RateLimitError(Exception):
    pass


class PayloadTooLargeError(Exception):
    pass


# Singleton
_orchestrator: Optional[LLMOrchestrator] = None


def get_orchestrator() -> LLMOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = LLMOrchestrator()
    return _orchestrator
