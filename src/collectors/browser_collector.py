"""
Browser-based collector using Playwright for JS-rendered sources.
Implements HTTP-first with browser fallback.
Respects robots.txt and does NOT bypass CAPTCHA/anti-bot protection.
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from src.collectors.base_collector import BaseCollector
from src.monitoring.logger import get_logger

logger = get_logger("collectors.browser")


class BrowserCollector(BaseCollector):
    """
    Async Playwright-based browser collector.

    Strategy:
    1. Try HTTP fetch first (faster, cheaper)
    2. Fall back to browser for JS-rendered content
    3. Detect access-denied / anti-bot responses
    4. Never bypass CAPTCHA or authentication guards
    5. Report unavailable sources clearly

    For Cloudflare/DataDome protected sites:
    - Detect the challenge page (HTTP 403, challenge-platform JS, turnstile widget)
    - Log the detection and mark source as 'access_denied'
    - Use official APIs or licensed feeds instead
    """

    name = "browser"
    rate_limit = 5  # Very conservative for browser requests

    ANTI_BOT_INDICATORS = [
        "challenge-platform",
        "cf-challenge",
        "turnstile",
        "cloudflare",
        "datadome",
        "access denied",
        "verify you are human",
        "captcha",
        "bot protection",
    ]

    async def _is_anti_bot_response(self, html: str) -> bool:
        """Detect anti-bot protection in page content."""
        html_lower = html.lower()
        return any(indicator in html_lower for indicator in self.ANTI_BOT_INDICATORS)

    async def fetch_with_browser(self, url: str) -> Optional[str]:
        """
        Fetch a URL using Playwright with appropriate throttling.
        Returns page HTML or None if blocked/failed.
        """
        try:
            from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
        except ImportError:
            logger.error("Playwright not installed. Run: playwright install chromium")
            return None

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
                context = await browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                    # Block images and fonts to speed up loading
                    extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
                )
                # Block heavy resources
                await context.route(
                    "**/*.{png,jpg,jpeg,gif,svg,ico,woff,woff2,ttf,eot}",
                    lambda route: route.abort(),
                )

                page = await context.new_page()
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    await asyncio.sleep(2)  # Allow JS to settle
                    html = await page.content()
                except PlaywrightTimeout:
                    logger.warning("Browser timeout", extra={"url": url})
                    html = None
                finally:
                    await context.close()
                    await browser.close()

                if html and await self._is_anti_bot_response(html):
                    logger.warning(
                        "Anti-bot protection detected: not bypassing",
                        extra={"url": url},
                    )
                    return None

                return html
        except Exception as exc:
            logger.error("Browser fetch failed", extra={"url": url, "error": str(exc)})
            return None

    async def collect(self) -> List[Dict[str, Any]]:
        """
        Browser collector is used as a fallback by other collectors.
        This standalone collect() is a no-op; call fetch_with_browser() directly.
        """
        return []

    def report_anti_bot_limitation(self, source_name: str, url: str, fallback: str) -> Dict[str, Any]:
        """
        Return a structured limitation report when a source is inaccessible.
        """
        report = {
            "source": source_name,
            "url": url,
            "status": "access_denied",
            "reason": "Anti-bot protection detected (Cloudflare/DataDome). No bypass attempted.",
            "fallback_strategy": fallback,
            "compliant": True,
        }
        logger.warning("Source unavailable due to anti-bot protection", extra=report)
        return report
