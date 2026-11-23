"""
Startup collector: discovers AI startups from multiple public sources:
1. Y Combinator companies directory (public API)
2. Hugging Face organizations (public API)
3. AI startup directories (public pages)

All sources are publicly accessible without authentication.
"""
from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.collectors.base_collector import BaseCollector
from src.config import settings
from src.monitoring.logger import get_logger

logger = get_logger("collectors.startup")
UTC = timezone.utc


class StartupCollector(BaseCollector):
    name = "startup"
    rate_limit = 15

    # ─────────────────────────────────────────────────────────────────────
    # Source A: Y Combinator public companies API
    # ─────────────────────────────────────────────────────────────────────
    async def _collect_yc(self, max_pages: int = 50) -> List[Dict[str, Any]]:
        """
        Y Combinator public Algolia search API.
        Filters for AI-related companies.
        Source: https://www.ycombinator.com/companies (powered by Algolia)
        """
        url = "https://45bwzj1sgc-dsn.algolia.net/1/indexes/*/queries"
        headers = {
            "X-Algolia-Application-Id": "45BWZJ1SGC",
            "X-Algolia-API-Key": "Yz86oa7T9Y9PNv2sqH3c6p6y0FdGAlzh7WcK9HCCitJq2b7JjCU2ZSr1aSpSfBQQ",
            "Content-Type": "application/json",
        }
        ai_tags = "Artificial Intelligence,Machine Learning,NLP,Computer Vision,Generative AI,LLM,Data Science"
        companies: List[Dict[str, Any]] = []

        for tag in ai_tags.split(","):
            page = 0
            while True:
                body = {
                    "requests": [
                        {
                            "indexName": "YCCompany_production",
                            "params": f"tagFilters=%5B%22{tag.replace(' ', '%20')}%22%5D&hitsPerPage=50&page={page}",
                        }
                    ]
                }
                data = await self.fetch(url, method="POST", json_body=body, headers=headers)
                if not isinstance(data, dict):
                    break
                hits = data.get("results", [{}])[0].get("hits", [])
                if not hits:
                    break
                for hit in hits:
                    name = hit.get("name", "")
                    if not name:
                        continue
                    slug = hit.get("slug", "")
                    source_url = f"https://www.ycombinator.com/companies/{slug}" if slug else f"https://www.ycombinator.com/companies?query={name}"
                    companies.append({
                        "entity_name": name,
                        "source_name": "Y Combinator",
                        "source_url": source_url,
                        "employee_count": None,
                        "description": hit.get("one_liner"),
                        "extra_data": {
                            "batch": hit.get("batch"),
                            "tags": hit.get("tags", []),
                            "status": hit.get("status"),
                            "location": hit.get("location"),
                        },
                        "collected_at": datetime.now(UTC).isoformat(),
                    })
                total_pages = data.get("results", [{}])[0].get("nbPages", 0)
                page += 1
                if page >= min(total_pages, max_pages):
                    break
                await asyncio.sleep(1.0)

            self._metrics.records_discovered += len(companies)
            logger.info(f"YC tag '{tag}': {len(companies)} companies collected so far")

        return companies

    # ─────────────────────────────────────────────────────────────────────
    # Source B: Hugging Face organizations
    # ─────────────────────────────────────────────────────────────────────
    async def _collect_huggingface_orgs(self, limit: int = 600) -> List[Dict[str, Any]]:
        """
        Extract unique AI organizations and labs deploying models on Hugging Face.
        Source: https://huggingface.co/api/models
        """
        orgs: List[Dict[str, Any]] = []
        seen: set = set()
        sort_criteria = ["downloads", "likes", "trendingScore"]

        for sort_by in sort_criteria:
            if len(orgs) >= limit:
                break
            url = "https://huggingface.co/api/models"
            params = {
                "limit": 500,
                "sort": sort_by,
                "direction": -1,
                "full": "false",
            }
            data = await self.fetch(url, params=params)
            if not isinstance(data, list):
                continue

            for model in data:
                model_id = model.get("id") or model.get("modelId") or ""
                if "/" in model_id:
                    org_name = model_id.split("/")[0]
                    if org_name and org_name not in seen:
                        seen.add(org_name)
                        source_url = f"https://huggingface.co/{org_name}"
                        desc = f"AI lab/organization with models on Hugging Face (e.g. {model_id})"
                        orgs.append({
                            "entity_name": org_name,
                            "source_name": "Hugging Face Ecosystem",
                            "source_url": source_url,
                            "employee_count": None,
                            "description": desc,
                            "extra_data": {
                                "featured_model": model_id,
                                "pipeline_tag": model.get("pipeline_tag"),
                                "downloads": model.get("downloads"),
                            },
                            "collected_at": datetime.now(UTC).isoformat(),
                        })
                        if len(orgs) >= limit:
                            break

            logger.info(f"HF orgs (sort={sort_by}): {len(orgs)} unique orgs collected")
            await asyncio.sleep(0.5)

        return orgs

    # ─────────────────────────────────────────────────────────────────────
    # Source B: GitHub AI organizations (public search API)
    # ─────────────────────────────────────────────────────────────────────
    async def _collect_github_ai_orgs(self, limit: int = 600) -> List[Dict[str, Any]]:
        """
        GitHub public search API for AI organizations.
        Source: https://api.github.com/search/users?q=...
        """
        token = settings.github_token
        headers: Dict[str, str] = {"Accept": "application/vnd.github.v3+json"}
        if token:
            headers["Authorization"] = f"token {token}"

        orgs: List[Dict[str, Any]] = []
        seen: set = set()
        ai_queries = [
            "artificial-intelligence", "machine-learning", "deep-learning",
            "generative-ai", "large-language-models", "computer-vision",
            "neural-networks", "natural-language-processing",
        ]

        for query in ai_queries:
            if len(orgs) >= limit:
                break
            for page in range(1, 4):
                if len(orgs) >= limit:
                    break
                url = "https://api.github.com/search/users"
                params = {
                    "q": f"{query} type:org",
                    "per_page": 30,
                    "page": page,
                }
                data = await self.fetch(url, params=params, headers=headers)
                if not isinstance(data, dict):
                    break
                items = data.get("items", [])
                if not items:
                    break
                for item in items:
                    login = item.get("login", "")
                    if login and login not in seen:
                        seen.add(login)
                        source_url = f"https://github.com/{login}"
                        orgs.append({
                            "entity_name": login,
                            "source_name": "GitHub AI Organizations",
                            "source_url": source_url,
                            "employee_count": None,
                            "description": f"AI organization on GitHub ({query})",
                            "extra_data": {
                                "github_id": item.get("id"),
                                "avatar_url": item.get("avatar_url"),
                                "topic": query,
                            },
                            "collected_at": datetime.now(UTC).isoformat(),
                        })
                await asyncio.sleep(1.0)

        logger.info(f"GitHub AI orgs: {len(orgs)} unique orgs collected")
        return orgs

    async def collect(self) -> List[Dict[str, Any]]:
        """Collect AI startups from all configured sources."""
        logger.info("Starting startup collection from multiple sources...")

        hf_task = asyncio.create_task(self._collect_huggingface_orgs(limit=600))
        gh_task = asyncio.create_task(self._collect_github_ai_orgs(limit=600))

        hf_results, gh_results = await asyncio.gather(
            hf_task, gh_task, return_exceptions=True
        )

        all_records: List[Dict[str, Any]] = []
        for result, source in [
            (hf_results, "Hugging Face"),
            (gh_results, "GitHub"),
        ]:
            if isinstance(result, Exception):
                logger.error(f"Source {source} failed", extra={"error": str(result)})
            else:
                all_records.extend(result)
                logger.info(f"{source}: {len(result)} records")

        logger.info(f"Total startups collected: {len(all_records)}")
        return all_records
