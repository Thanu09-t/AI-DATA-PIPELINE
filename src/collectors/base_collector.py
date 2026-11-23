"""
Base collector: shared async HTTP logic, rate limiting, retries, checkpoints.
"""
from __future__ import annotations

import asyncio
import json
import random
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional

import aiohttp
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
    before_sleep_log,
    RetryError,
)

from src.config import settings
from src.monitoring.logger import get_logger
from src.monitoring.metrics import metrics

logger = get_logger("collectors.base")
UTC = timezone.utc

RETRY_STATUS_CODES = {429, 500, 502, 503, 504}

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; AIIntelligenceBot/1.0; "
        "+https://github.com/ai-intelligence-ingestion)"
    ),
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "en-US,en;q=0.9",
}


class RateLimiter:
    """Token-bucket rate limiter for async code."""

    def __init__(self, rate: int, per: float = 60.0):
        self.rate = rate
        self.per = per
        self._allowance = float(rate)
        self._last_check = time.monotonic()
        self._lock: Optional[asyncio.Lock] = None

    async def acquire(self) -> None:
        if self._lock is None:
            self._lock = asyncio.Lock()
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_check
            self._last_check = now
            self._allowance += elapsed * (self.rate / self.per)
            if self._allowance > self.rate:
                self._allowance = float(self.rate)
            if self._allowance < 1.0:
                sleep_time = (1.0 - self._allowance) * (self.per / self.rate)
                await asyncio.sleep(sleep_time)
                self._allowance = 0.0
            else:
                self._allowance -= 1.0


class CheckpointManager:
    """Simple file-based checkpoint for resumable collection."""

    def __init__(self, name: str):
        self.path = settings.raw_dir / f"{name}.checkpoint.json"
        self._data: Dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                with open(self.path) as f:
                    self._data = json.load(f)
            except Exception:
                self._data = {}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w") as f:
            json.dump(self._data, f)

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self.save()

    def reset(self) -> None:
        self._data = {}
        if self.path.exists():
            self.path.unlink()


class BaseCollector(ABC):
    """
    Abstract base for all data collectors.
    Provides shared session management, rate limiting, retry logic,
    and checkpoint-based recovery.
    """

    name: str = "base"
    rate_limit: int = 10  # requests per minute

    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
        self._rate_limiter = RateLimiter(rate=self.rate_limit)
        self._checkpoint = CheckpointManager(self.name)
        self._metrics = metrics.pipeline(self.name)
        self._semaphore: Optional[asyncio.Semaphore] = None
        logger.info(f"Collector initialized: {self.name}")

    async def __aenter__(self) -> "BaseCollector":
        connector = aiohttp.TCPConnector(
            limit=settings.max_concurrent_requests,
            ttl_dns_cache=300,
            enable_cleanup_closed=True,
            ssl=False,
        )
        timeout = aiohttp.ClientTimeout(total=30, connect=10, sock_read=20)
        self._session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers=DEFAULT_HEADERS,
        )
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._session:
            await self._session.close()

    async def fetch(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        method: str = "GET",
        json_body: Optional[Dict] = None,
        return_text: bool = False,
    ) -> Optional[Any]:
        """
        Fetch a URL with rate limiting, retry, and circuit-breaker logic.
        Returns parsed JSON dict, raw text, or None on failure.
        """
        await self._rate_limiter.acquire()
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(settings.max_concurrent_requests)
        async with self._semaphore:
            attempt = 0
            base_delay = settings.retry_base_delay
            max_delay = settings.retry_max_delay
            last_exc: Optional[Exception] = None

            for attempt in range(settings.max_retries + 1):
                try:
                    self._metrics.records_discovered  # touch metric
                    kwargs: Dict[str, Any] = {
                        "params": params,
                        "headers": headers,
                    }
                    if json_body:
                        kwargs["json"] = json_body

                    assert self._session is not None
                    async with self._session.request(method, url, **kwargs) as resp:
                        if resp.status == 429:
                            self._metrics.rate_limit_events += 1
                            retry_after = float(resp.headers.get("Retry-After", base_delay * (2 ** attempt)))
                            jitter = random.uniform(0, 2)
                            wait = min(retry_after + jitter, max_delay)
                            logger.warning(
                                "Rate limited (429)",
                                extra={"url": url, "wait_seconds": wait, "attempt": attempt},
                            )
                            await asyncio.sleep(wait)
                            continue

                        if resp.status in {500, 502, 503, 504}:
                            wait = min(base_delay * (2 ** attempt) + random.uniform(0, 1), max_delay)
                            logger.warning(
                                f"Server error {resp.status}",
                                extra={"url": url, "wait": wait, "attempt": attempt},
                            )
                            await asyncio.sleep(wait)
                            continue

                        if resp.status == 403:
                            logger.warning("Access denied (403)", extra={"url": url})
                            return None

                        if resp.status == 404:
                            logger.debug("Not found (404)", extra={"url": url})
                            return None

                        if resp.status >= 400:
                            logger.warning(
                                f"HTTP error {resp.status}", extra={"url": url}
                            )
                            return None

                        if return_text:
                            return await resp.text()

                        content_type = resp.headers.get("Content-Type", "")
                        if "json" in content_type:
                            return await resp.json(content_type=None)
                        return await resp.text()

                except aiohttp.ClientConnectorError as exc:
                    last_exc = exc
                    wait = min(base_delay * (2 ** attempt), max_delay)
                    logger.warning("Connection error", extra={"url": url, "error": str(exc)})
                    await asyncio.sleep(wait)
                except asyncio.TimeoutError:
                    wait = min(base_delay * (2 ** attempt), max_delay)
                    logger.warning("Timeout", extra={"url": url, "attempt": attempt})
                    await asyncio.sleep(wait)
                except Exception as exc:
                    last_exc = exc
                    logger.error("Unexpected fetch error", extra={"url": url, "error": str(exc)})
                    break

            self._metrics.errors += 1
            logger.error(
                "Max retries exceeded",
                extra={"url": url, "attempts": attempt + 1, "error": str(last_exc)},
            )
            return None

    @abstractmethod
    async def collect(self) -> List[Dict[str, Any]]:
        """Collect records and return a list of raw dicts."""
        ...

    async def collect_paginated(
        self,
        url: str,
        params: Dict[str, Any],
        page_key: str = "page",
        results_key: str = "results",
        max_pages: int = 100,
    ) -> AsyncIterator[List[Dict[str, Any]]]:
        """Generic paginator: yields page results until exhausted."""
        page = self._checkpoint.get("page", 0)
        for p in range(page, page + max_pages):
            params[page_key] = p
            data = await self.fetch(url, params=params)
            if not data:
                break
            results = data if isinstance(data, list) else data.get(results_key, [])
            if not results:
                break
            yield results
            self._checkpoint.set("page", p + 1)
            if len(results) < params.get("per_page", params.get("limit", 50)):
                break  # Last page
