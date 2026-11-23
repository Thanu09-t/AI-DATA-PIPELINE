"""
arXiv API collector: fetches AI research papers using the official arXiv API.
Targets cs.AI, cs.LG, cs.CL, cs.CV, cs.RO, stat.ML categories.
No authentication required.
"""
from __future__ import annotations

import asyncio
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import aiohttp

from src.collectors.base_collector import BaseCollector
from src.config import settings
from src.monitoring.logger import get_logger
from src.processing.enrichment import extract_github_url

logger = get_logger("collectors.research")

ARXIV_API = "https://export.arxiv.org/api/query"
ARXIV_NS = "http://www.w3.org/2005/Atom"
ARXIV_NS2 = "http://arxiv.org/schemas/atom"


class ResearchCollector(BaseCollector):
    name = "research"
    rate_limit = 20  # arXiv recommends ≤ 3 req/sec; we're conservative

    def __init__(self):
        super().__init__()

    def _parse_entry(self, entry: ET.Element) -> Optional[Dict[str, Any]]:
        """Parse a single arXiv API entry XML element."""
        ns = {"atom": ARXIV_NS, "arxiv": ARXIV_NS2}

        def find_text(tag: str) -> Optional[str]:
            el = entry.find(tag, ns)
            return el.text.strip() if el is not None and el.text else None

        title = find_text("atom:title")
        if not title:
            return None
        title = " ".join(title.split())  # collapse whitespace

        # Paper URL
        paper_url: Optional[str] = None
        for link in entry.findall("atom:link", ns):
            if link.get("rel") == "alternate":
                paper_url = link.get("href")
                break
        if not paper_url:
            id_el = entry.find("atom:id", ns)
            paper_url = id_el.text.strip() if id_el is not None and id_el.text else None

        if not paper_url:
            return None

        # ArXiv ID
        arxiv_id: Optional[str] = None
        m = re.search(r"abs/([0-9]+\.[0-9]+(?:v\d+)?)", paper_url)
        if m:
            arxiv_id = m.group(1)

        # Authors
        authors = []
        for author_el in entry.findall("atom:author", ns):
            name_el = author_el.find("atom:name", ns)
            if name_el is not None and name_el.text:
                authors.append(name_el.text.strip())

        # Abstract
        abstract = find_text("atom:summary") or ""

        # Published date
        published_str = find_text("atom:published")
        published_dt: Optional[datetime] = None
        if published_str:
            try:
                published_dt = datetime.fromisoformat(
                    published_str.replace("Z", "+00:00")
                )
            except ValueError:
                pass

        # GitHub URL from abstract
        github_url = extract_github_url(abstract)

        # Comments (sometimes contain GitHub links)
        comment_el = entry.find("arxiv:comment", ns)
        if not github_url and comment_el is not None and comment_el.text:
            github_url = extract_github_url(comment_el.text)

        return {
            "title": title,
            "authors": authors,
            "paper_url": paper_url,
            "arxiv_id": arxiv_id,
            "abstract": abstract,
            "github_url": github_url,
            "github_stars": None,
            "github_stars_collected_at": None,
            "github_enriched": False,
            "published_date": published_dt,
            "source_name": "arXiv",
        }

    async def _fetch_category(
        self, category: str, max_results: int
    ) -> List[Dict[str, Any]]:
        """Fetch papers for a single arXiv category with pagination."""
        papers: List[Dict[str, Any]] = []
        batch = 200  # arXiv API batch per request
        start = self._checkpoint.get(f"arxiv_{category}_start", 0)

        for offset in range(start, max_results, batch):
            params = {
                "search_query": f"cat:{category}",
                "start": offset,
                "max_results": min(batch, max_results - offset),
                "sortBy": "submittedDate",
                "sortOrder": "descending",
            }
            logger.info(
                f"Fetching arXiv {category}",
                extra={"offset": offset, "batch": batch},
            )
            response = await self.fetch(ARXIV_API, params=params, return_text=True)
            if not response:
                break

            try:
                root = ET.fromstring(response)
            except ET.ParseError as exc:
                logger.error("XML parse error", extra={"error": str(exc)})
                break

            entries = root.findall(f"{{{ARXIV_NS}}}entry")
            if not entries:
                break

            page_papers = []
            for entry in entries:
                parsed = self._parse_entry(entry)
                if parsed:
                    page_papers.append(parsed)

            papers.extend(page_papers)
            self._checkpoint.set(f"arxiv_{category}_start", offset + batch)

            logger.info(
                f"arXiv {category}: fetched {len(page_papers)} papers (total: {len(papers)})"
            )
            self._metrics.records_discovered += len(page_papers)

            # Respect arXiv rate limit: 3 seconds between requests
            await asyncio.sleep(3.5)

            if len(entries) < batch:
                break  # Last page

        return papers

    async def collect(self) -> List[Dict[str, Any]]:
        """Collect papers from all configured arXiv categories."""
        categories = settings.arxiv_category_list
        target = settings.target_papers
        per_category = max(300, target // len(categories) + 100)

        all_papers: List[Dict[str, Any]] = []
        seen_arxiv_ids: set = set()

        for category in categories:
            category_papers = await self._fetch_category(category, per_category)
            for p in category_papers:
                arxiv_id = p.get("arxiv_id")
                url = p.get("paper_url", "")
                key = arxiv_id or url
                if key not in seen_arxiv_ids:
                    seen_arxiv_ids.add(key)
                    all_papers.append(p)
            logger.info(
                f"Category {category} complete",
                extra={"count": len(category_papers), "total": len(all_papers)},
            )
            if len(all_papers) >= target:
                break

        logger.info(f"Research collection complete: {len(all_papers)} unique papers")
        return all_papers
