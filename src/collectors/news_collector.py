"""
News collector: monitors five AI news sources via RSS feeds and public APIs.

Sources selected for reliability, public RSS availability, and AI content:
1. TechCrunch AI - RSS feed, authoritative tech news
2. VentureBeat AI - RSS feed, AI-focused coverage
3. MIT Technology Review - RSS feed, research-grade AI journalism
4. The Decoder - RSS feed, AI-specific outlet
5. MarkTechPost - RSS feed, AI research and industry news

All sources use publicly available RSS feeds: no authentication required.
"""
from __future__ import annotations

import asyncio
import hashlib
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

from src.collectors.base_collector import BaseCollector
from src.config import settings
from src.monitoring.logger import get_logger
from src.processing.date_normalizer import parse_date_string, extract_date_from_html_meta

logger = get_logger("collectors.news")
UTC = timezone.utc

NEWS_SOURCES = [
    {
        "name": "TechCrunch AI",
        "rss": "https://techcrunch.com/category/artificial-intelligence/feed/",
        "base_url": "https://techcrunch.com",
        "rationale": "Leading tech publication with dedicated AI section and reliable RSS feed",
    },
    {
        "name": "VentureBeat AI",
        "rss": "https://venturebeat.com/category/ai/feed/",
        "base_url": "https://venturebeat.com",
        "rationale": "AI-focused tech journalism with consistent publication timestamps",
    },
    {
        "name": "MIT Technology Review",
        "rss": "https://www.technologyreview.com/feed/",
        "base_url": "https://www.technologyreview.com",
        "rationale": "Research-backed AI coverage with verified publication dates",
    },
    {
        "name": "The Decoder",
        "rss": "https://the-decoder.com/feed/",
        "base_url": "https://the-decoder.com",
        "rationale": "AI-only outlet with daily coverage and reliable RSS timestamps",
    },
    {
        "name": "MarkTechPost",
        "rss": "https://www.marktechpost.com/feed/",
        "base_url": "https://www.marktechpost.com",
        "rationale": "AI research paper summaries and industry news with RSS support",
    },
]


def _url_hash(url: str) -> str:
    return hashlib.sha256(url.strip().lower().encode()).hexdigest()


class NewsCollector(BaseCollector):
    name = "news"
    rate_limit = 10  # Conservative to avoid rate limiting

    async def _fetch_rss(self, source: Dict[str, str]) -> List[Dict[str, Any]]:
        """Fetch and parse an RSS feed, returning article records."""
        rss_url = source["rss"]
        source_name = source["name"]

        xml_text = await self.fetch(rss_url, return_text=True)
        if not xml_text:
            logger.warning(f"RSS fetch failed: {source_name}", extra={"url": rss_url})
            return []

        articles: List[Dict[str, Any]] = []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            logger.error(f"RSS XML parse error: {source_name}", extra={"error": str(exc)})
            return []

        # Support both RSS 2.0 and Atom
        # RSS 2.0: channel/item
        items = root.findall(".//item")
        # Atom: entry
        if not items:
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            items = root.findall(".//atom:entry", ns) or root.findall(".//entry")

        now = datetime.now(UTC)

        for item in items:
            def tag(name: str) -> Optional[str]:
                # Try with and without namespace
                el = item.find(name)
                if el is None:
                    # Try common namespaces
                    for ns_prefix in ["", "atom:", "dc:"]:
                        el = item.find(f"{ns_prefix}{name}")
                        if el is not None:
                            break
                return el.text.strip() if el is not None and el.text else None

            title = tag("title")
            if not title:
                continue

            link = tag("link")
            if not link:
                # Atom uses href attribute
                link_el = item.find("link")
                if link_el is not None:
                    link = link_el.get("href")

            if not link:
                continue

            # Try multiple date fields
            pub_date_str = (
                tag("pubDate") or tag("published") or tag("updated") or
                tag("dc:date") or tag("date")
            )
            pub_dt: Optional[datetime] = None
            pub_verified = False
            pub_method = "not_found"

            if pub_date_str:
                pub_dt, pub_verified, pub_method = parse_date_string(pub_date_str, now=now)

            # Description/summary
            description = tag("description") or tag("summary") or ""
            if description:
                # Strip HTML from description
                try:
                    description = BeautifulSoup(description, "lxml").get_text(separator=" ")[:1000]
                except Exception:
                    description = description[:1000]

            articles.append({
                "title": title,
                "full_text": description,
                "source_name": source_name,
                "source_url": link,
                "url_hash": _url_hash(link),
                "published_at": pub_dt,
                "published_at_verified": pub_verified,
                "published_at_method": pub_method,
                "discovered_at": now,
                "collected_at": now,
                "is_fresh": False,  # Will be set by freshness filter
                "extra_data": {"source_rationale": source["rationale"]},
            })

        logger.info(
            f"RSS parsed: {source_name}",
            extra={"articles": len(articles), "url": rss_url},
        )
        return articles

    async def collect(self) -> List[Dict[str, Any]]:
        """Collect news from all five sources concurrently."""
        logger.info(f"Starting news collection from {len(NEWS_SOURCES)} sources...")

        tasks = [self._fetch_rss(source) for source in NEWS_SOURCES]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_articles: List[Dict[str, Any]] = []
        for result, source in zip(results, NEWS_SOURCES):
            if isinstance(result, Exception):
                logger.error(
                    f"News source failed: {source['name']}",
                    extra={"error": str(result)},
                )
            else:
                all_articles.extend(result)
                logger.info(f"{source['name']}: {len(result)} articles")

        self._metrics.records_discovered = len(all_articles)
        logger.info(f"Total news articles collected: {len(all_articles)}")
        return all_articles
