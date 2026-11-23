"""
Product collector: discovers AI products from public sources:
1. Hugging Face Models (public API: largest AI model/product catalog)
2. Hugging Face Spaces (public API: AI demo/product catalog)
3. GitHub AI repositories (AI tools/products)

These are the most reliably accessible public AI product sources.
Product Hunt requires paid API access and is noted as a limitation.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.collectors.base_collector import BaseCollector
from src.config import settings
from src.monitoring.logger import get_logger

logger = get_logger("collectors.product")
UTC = timezone.utc

PRICING_KEYWORDS = {
    "FREEMIUM": ["freemium", "free tier", "free plan", "free trial", "pro plan", "upgrade"],
    "ENTERPRISE": ["enterprise", "contact sales", "custom pricing", "team plan"],
    "PAID": ["paid", "subscription", "pricing", "per month", "per year", "purchase"],
    "FREE": ["free", "open source", "open-source", "mit license", "apache", "gpl"],
}


def infer_pricing(text: str) -> str:
    """Infer pricing model from text evidence. Returns 'Not listed' if ambiguous or missing."""
    if not text:
        return "Not listed"
    text_lower = text.lower()
    for model, keywords in PRICING_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            return model
    return "Not listed"


class ProductCollector(BaseCollector):
    name = "product"
    rate_limit = 20

    # ─────────────────────────────────────────────────────────────────────
    # Source A: Hugging Face Models
    # ─────────────────────────────────────────────────────────────────────
    async def _collect_hf_models(self, limit: int = 1100) -> List[Dict[str, Any]]:
        """
        Hugging Face models API (public, no auth required for basic access).
        Source: https://huggingface.co/api/models
        Filters for most popular AI models as "products".
        """
        products: List[Dict[str, Any]] = []
        per_page = 100
        # Sort by most downloaded = most deployed/used products
        ai_tasks = [
            "text-generation", "text-classification", "token-classification",
            "question-answering", "summarization", "image-classification",
            "object-detection", "image-to-text", "text-to-image",
            "translation", "conversational", "feature-extraction",
        ]

        for task in ai_tasks:
            if len(products) >= limit:
                break
            url = f"https://huggingface.co/api/models"
            params = {
                "pipeline_tag": task,
                "limit": min(per_page, limit - len(products)),
                "sort": "downloads",
                "direction": -1,
                "full": "false",
            }
            data = await self.fetch(url, params=params)
            if not isinstance(data, list):
                continue

            for model in data:
                model_id = model.get("modelId") or model.get("id", "")
                if not model_id:
                    continue
                # Derive company/creator from the part before the slash, fallback to 'Unknown'
                parts = model_id.split("/", 1)
                org = parts[0].strip() if len(parts) > 1 and parts[0].strip() else "Unknown"
                name = parts[-1].strip() if parts[-1].strip() else model_id
                source_url = f"https://huggingface.co/{model_id}"

                # Real pricing only if explicitly confirmed by tags, else 'Not listed'
                tags = model.get("tags", [])
                tag_str = " ".join(t.lower() for t in tags)
                if any(t in tag_str for t in ["open-source", "license:mit", "license:apache", "license:bsd", "license:gpl"]):
                    pricing = "FREE"
                elif any(t in tag_str for t in ["commercial", "subscription", "paid"]):
                    pricing = "PAID"
                else:
                    pricing = "Not listed"

                products.append({
                    "product_name": name,
                    "company_name": org,
                    "entity_name": name,
                    "startup_name": org,
                    "source_name": "Hugging Face Models",
                    "source_url": source_url,
                    "pricing_model": pricing,
                    "description": f"{task} model: {model_id}",
                    "extra_data": {
                        "model_id": model_id,
                        "task": task,
                        "downloads": model.get("downloads"),
                        "likes": model.get("likes"),
                        "tags": tags,
                        "library_name": model.get("library_name"),
                    },
                    "collected_at": datetime.now(UTC).isoformat(),
                })

            logger.info(f"HF Models task '{task}': {len(products)} products so far")
            await asyncio.sleep(0.5)

        return products[:limit]

    # ─────────────────────────────────────────────────────────────────────
    # Source B: Hugging Face Spaces (AI demos / apps)
    # ─────────────────────────────────────────────────────────────────────
    async def _collect_hf_spaces(self, limit: int = 400) -> List[Dict[str, Any]]:
        """
        Hugging Face Spaces: public AI web applications.
        Source: https://huggingface.co/api/spaces
        """
        products: List[Dict[str, Any]] = []
        url = "https://huggingface.co/api/spaces"
        params = {
            "limit": min(100, limit),
            "sort": "likes",
            "direction": -1,
            "full": "false",
        }

        page_count = 0
        while len(products) < limit:
            params["skip"] = page_count * params["limit"]
            data = await self.fetch(url, params=params)
            if not isinstance(data, list) or not data:
                break

            for space in data:
                space_id = space.get("id", "")
                if not space_id:
                    continue
                parts = space_id.split("/", 1)
                org = parts[0].strip() if len(parts) > 1 and parts[0].strip() else "Unknown"
                name = parts[-1].strip() if parts[-1].strip() else space_id
                source_url = f"https://huggingface.co/spaces/{space_id}"

                sdk = space.get("sdk", "")
                pricing = "FREE"  # Hugging Face public community spaces are free to use

                products.append({
                    "product_name": name,
                    "company_name": org,
                    "entity_name": name,
                    "startup_name": org,
                    "source_name": "Hugging Face Spaces",
                    "source_url": source_url,
                    "pricing_model": pricing,
                    "description": f"AI Space: {space_id} ({sdk})",
                    "extra_data": {
                        "space_id": space_id,
                        "sdk": sdk,
                        "likes": space.get("likes"),
                        "tags": space.get("tags", []),
                    },
                    "collected_at": datetime.now(UTC).isoformat(),
                })

            page_count += 1
            logger.info(f"HF Spaces page {page_count}: {len(products)} products so far")

            if len(data) < params["limit"]:
                break
            await asyncio.sleep(0.5)

        return products[:limit]

    # ─────────────────────────────────────────────────────────────────────
    # Source C: GitHub top AI repos (as AI tool products)
    # ─────────────────────────────────────────────────────────────────────
    async def _collect_github_ai_tools(self, limit: int = 300) -> List[Dict[str, Any]]:
        """
        GitHub search API for top AI tool repositories.
        These represent AI products/frameworks widely used in the community.
        Source: https://api.github.com/search/repositories
        """
        token = settings.github_token
        headers: Dict[str, str] = {"Accept": "application/vnd.github.v3+json"}
        if token:
            headers["Authorization"] = f"token {token}"

        products: List[Dict[str, Any]] = []
        queries = [
            "AI tool stars:>500 topic:artificial-intelligence",
            "LLM library stars:>200 topic:large-language-models",
            "machine-learning framework stars:>500",
            "computer-vision toolkit stars:>200",
            "NLP library stars:>300 topic:nlp",
        ]

        for query in queries:
            if len(products) >= limit:
                break
            url = "https://api.github.com/search/repositories"
            params = {
                "q": query,
                "per_page": 30,
                "sort": "stars",
                "order": "desc",
            }
            data = await self.fetch(url, params=params, headers=headers)
            if not isinstance(data, dict):
                continue
            items = data.get("items", [])
            for repo in items:
                name = repo.get("name", "")
                if not name:
                    continue
                owner = repo.get("owner", {}).get("login", "") or "Unknown"
                source_url = repo.get("html_url", f"https://github.com/{owner}/{name}")
                desc = repo.get("description", "") or ""
                # GitHub open-source repos with license are free, otherwise infer or Not listed
                license_info = repo.get("license")
                if license_info:
                    pricing = "FREE"
                else:
                    pricing = infer_pricing(desc)

                products.append({
                    "product_name": name,
                    "company_name": owner,
                    "entity_name": name,
                    "startup_name": owner,
                    "source_name": "GitHub AI Tools",
                    "source_url": source_url,
                    "pricing_model": pricing,
                    "description": desc[:300] if desc else None,
                    "extra_data": {
                        "stars": repo.get("stargazers_count"),
                        "forks": repo.get("forks_count"),
                        "language": repo.get("language"),
                        "topics": repo.get("topics", []),
                    },
                    "collected_at": datetime.now(UTC).isoformat(),
                })
            await asyncio.sleep(2.0)

        return products[:limit]

    async def collect(self) -> List[Dict[str, Any]]:
        """Collect AI products from all configured sources."""
        logger.info("Starting product collection...")

        hf_models_task = asyncio.create_task(self._collect_hf_models(limit=1100))
        hf_spaces_task = asyncio.create_task(self._collect_hf_spaces(limit=200))
        gh_task = asyncio.create_task(self._collect_github_ai_tools(limit=100))

        results = await asyncio.gather(
            hf_models_task, hf_spaces_task, gh_task, return_exceptions=True
        )

        all_records: List[Dict[str, Any]] = []
        for result, source in [
            (results[0], "HF Models"),
            (results[1], "HF Spaces"),
            (results[2], "GitHub AI Tools"),
        ]:
            if isinstance(result, Exception):
                logger.error(f"Source {source} failed", extra={"error": str(result)})
            else:
                all_records.extend(result)
                logger.info(f"{source}: {len(result)} products")

        logger.info(f"Total products collected: {len(all_records)}")
        self._metrics.records_discovered = len(all_records)
        return all_records
