"""
GitHub API collector: enriches research papers with repository star counts.
Uses GitHub REST API v3 with token authentication.
Respects rate limits (5000 req/hr with token, 60/hr without).
"""
from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.collectors.base_collector import BaseCollector
from src.config import settings
from src.monitoring.logger import get_logger

logger = get_logger("collectors.github")

GITHUB_API = "https://api.github.com"
UTC = timezone.utc


def parse_github_repo(url: str) -> Optional[tuple[str, str]]:
    """Extract (owner, repo) from a GitHub URL."""
    patterns = [
        re.compile(r"github\.com/([a-zA-Z0-9_\-\.]+)/([a-zA-Z0-9_\-\.]+?)(?:\.git)?(?:/|$)"),
    ]
    for pat in patterns:
        m = pat.search(url)
        if m:
            owner = m.group(1)
            repo = m.group(2).rstrip("/")
            # Exclude GitHub organization pages (no repo)
            if repo and repo not in {"issues", "pulls", "releases", "wiki"}:
                return owner, repo
    return None


class GitHubCollector(BaseCollector):
    name = "github"
    rate_limit = 25  # conservative: well below 60/min limit with token

    def __init__(self):
        super().__init__()
        self._token = settings.github_token
        self._auth_headers: Dict[str, str] = {}
        if self._token:
            self._auth_headers = {
                "Authorization": f"token {self._token}",
                "Accept": "application/vnd.github.v3+json",
            }
        else:
            logger.warning("No GITHUB_TOKEN configured: rate limit is 60 req/hr")

    async def get_repo_stars(self, github_url: str) -> Optional[Dict[str, Any]]:
        """Fetch star count and metadata for a single GitHub repository."""
        parsed = parse_github_repo(github_url)
        if not parsed:
            logger.debug("Could not parse GitHub URL", extra={"url": github_url})
            return None

        owner, repo = parsed
        api_url = f"{GITHUB_API}/repos/{owner}/{repo}"
        data = await self.fetch(api_url, headers=self._auth_headers)

        if not isinstance(data, dict):
            return None

        return {
            "github_url": f"https://github.com/{owner}/{repo}",
            "github_stars": data.get("stargazers_count"),
            "github_forks": data.get("forks_count"),
            "github_open_issues": data.get("open_issues_count"),
            "github_language": data.get("language"),
            "github_stars_collected_at": datetime.now(UTC).isoformat(),
            "github_enriched": True,
        }

    async def enrich_papers(
        self, papers: List[Dict[str, Any]], batch_size: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Enrich paper records with GitHub star counts.
        Only enriches records that have a github_url set.
        """
        total = len(papers)
        enriched_count = 0
        skipped = 0
        consecutive_failures = 0
        max_enrichments = 1000 if self._token else 40

        for i, paper in enumerate(papers):
            if enriched_count >= max_enrichments:
                logger.info(f"GitHub rate limit safety cap reached ({max_enrichments} repos enriched)")
                break

            if consecutive_failures >= 5:
                logger.warning("GitHub rate limit hit repeatedly (5 consecutive failures): stopping enrichment")
                break

            gh_url = paper.get("github_url")
            if not gh_url:
                skipped += 1
                continue

            # Skip already enriched
            if paper.get("github_enriched"):
                enriched_count += 1
                continue

            stats = await self.get_repo_stars(gh_url)
            if stats:
                paper.update(stats)
                enriched_count += 1
                consecutive_failures = 0
                logger.debug(
                    "GitHub enriched",
                    extra={
                        "title": paper.get("title", "")[:60],
                        "stars": stats.get("github_stars"),
                    },
                )
            else:
                paper["github_enriched"] = False
                consecutive_failures += 1

            if i > 0 and i % batch_size == 0:
                logger.info(
                    f"GitHub enrichment progress: {i}/{total} papers, {enriched_count} enriched"
                )
                # Avoid hitting rate limit: small pause every batch
                await asyncio.sleep(1.0)

        logger.info(
            "GitHub enrichment complete",
            extra={
                "total_papers": total,
                "enriched": enriched_count,
                "no_github_url": skipped,
            },
        )
        return papers

    async def collect(self) -> List[Dict[str, Any]]:
        """Standalone collect: not used directly; use enrich_papers instead."""
        return []
