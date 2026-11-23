"""
Job collector: monitors five AI job sources.

Sources selected for public accessibility and AI job concentration:
1. Greenhouse public job boards (via public API endpoint)
2. Lever public job boards (via public API endpoint)
3. Y Combinator Work at a Startup (public JSON API)
4. Ashby public job boards (public API)
5. Hacker News "Who is Hiring?" (public HN API: monthly thread)

Sources that use anti-bot protection (Wellfound) are noted as limitations.
All selected sources expose public, machine-readable endpoints.
"""
from __future__ import annotations

import asyncio
import hashlib
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.collectors.base_collector import BaseCollector
from src.config import settings
from src.monitoring.logger import get_logger
from src.processing.date_normalizer import parse_date_string
from src.processing.validators import classify_role_family

logger = get_logger("collectors.job")
UTC = timezone.utc


def _url_hash(url: str) -> str:
    return hashlib.sha256(url.strip().lower().encode()).hexdigest()


# Top AI companies with public Greenhouse job boards
GREENHOUSE_AI_COMPANIES = [
    ("openai", "OpenAI"),
    ("anthropic", "Anthropic"),
    ("cohere", "Cohere"),
    ("scale-ai", "Scale AI"),
    ("huggingface", "Hugging Face"),
    ("mistral", "Mistral AI"),
    ("databricks", "Databricks"),
    ("weights-biases", "Weights & Biases"),
    ("stability-ai", "Stability AI"),
    ("together-ai", "Together AI"),
    ("modal-labs", "Modal Labs"),
    ("replicate", "Replicate"),
    ("deepmind", "Google DeepMind"),
    ("ai21-labs", "AI21 Labs"),
    ("aleph-alpha", "Aleph Alpha"),
    ("adept", "Adept AI"),
    ("inflection-ai", "Inflection AI"),
    ("character-ai", "Character.AI"),
    ("runway", "Runway"),
    ("synthesis-ai", "Synthesis AI"),
]

LEVER_AI_COMPANIES = [
    ("anthropic", "Anthropic"),
    ("scale", "Scale AI"),
    ("coreweave", "CoreWeave"),
    ("lambda-labs", "Lambda Labs"),
    ("lightricks", "Lightricks"),
    ("jasper", "Jasper AI"),
    ("copy-ai", "Copy.ai"),
    ("notion", "Notion"),
    ("linear", "Linear"),
    ("retool", "Retool"),
]


class JobCollector(BaseCollector):
    name = "job"
    rate_limit = 10

    # ─────────────────────────────────────────────────────────────────────
    # Source A: Greenhouse public job board API
    # ─────────────────────────────────────────────────────────────────────
    async def _collect_greenhouse(self) -> List[Dict[str, Any]]:
        """
        Greenhouse public job board API: no authentication required.
        URL pattern: https://boards-api.greenhouse.io/v1/boards/{company}/jobs
        """
        jobs: List[Dict[str, Any]] = []
        now = datetime.now(UTC)

        for slug, company_name in GREENHOUSE_AI_COMPANIES:
            url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
            data = await self.fetch(url, params={"content": "true"})
            if not isinstance(data, dict):
                # Try alternate URL format
                url2 = f"https://boards-api.greenhouse.io/v1/boards/{slug.replace('-', '')}/jobs"
                data = await self.fetch(url2, params={"content": "true"})

            if not isinstance(data, dict):
                logger.debug(f"Greenhouse: no data for {company_name}")
                continue

            gh_jobs = data.get("jobs", [])
            for job in gh_jobs:
                title = job.get("title", "")
                if not title:
                    continue
                job_url = job.get("absolute_url") or f"https://boards.greenhouse.io/{slug}/jobs/{job.get('id', '')}"
                updated_at_str = job.get("updated_at") or job.get("created_at")
                pub_dt: Optional[datetime] = None
                pub_verified = False
                pub_method = "not_found"
                if updated_at_str:
                    pub_dt, pub_verified, pub_method = parse_date_string(updated_at_str, now=now)

                # Location
                location = ""
                loc_data = job.get("location", {})
                if isinstance(loc_data, dict):
                    location = loc_data.get("name", "")
                elif isinstance(loc_data, str):
                    location = loc_data

                is_remote = "remote" in (location or "").lower() or "remote" in title.lower()

                jobs.append({
                    "title": title,
                    "company": company_name,
                    "source_name": "Greenhouse",
                    "source_url": job_url,
                    "url_hash": _url_hash(job_url),
                    "published_at": pub_dt,
                    "published_at_verified": pub_verified,
                    "published_at_method": pub_method,
                    "discovered_at": now,
                    "collected_at": now,
                    "is_remote": is_remote,
                    "role_family": classify_role_family(title),
                    "location": location,
                    "is_fresh": False,
                    "extra_data": {
                        "departments": [d.get("name") for d in job.get("departments", [])],
                        "offices": [o.get("name") for o in job.get("offices", [])],
                    },
                })

            logger.info(f"Greenhouse {company_name}: {len(gh_jobs)} jobs")
            await asyncio.sleep(0.5)

        return jobs

    # ─────────────────────────────────────────────────────────────────────
    # Source B: Lever public job board API
    # ─────────────────────────────────────────────────────────────────────
    async def _collect_lever(self) -> List[Dict[str, Any]]:
        """
        Lever public job posting API: no auth needed.
        URL: https://api.lever.co/v0/postings/{company}?mode=json
        """
        jobs: List[Dict[str, Any]] = []
        now = datetime.now(UTC)

        for slug, company_name in LEVER_AI_COMPANIES:
            url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
            data = await self.fetch(url)
            if not isinstance(data, list):
                logger.debug(f"Lever: no data for {company_name}")
                continue

            for posting in data:
                title = posting.get("text", "")
                if not title:
                    continue
                job_url = posting.get("hostedUrl") or posting.get("applyUrl", "")
                created_at = posting.get("createdAt")
                pub_dt: Optional[datetime] = None
                pub_verified = False
                pub_method = "not_found"
                if created_at:
                    # Lever uses Unix milliseconds
                    try:
                        pub_dt = datetime.fromtimestamp(int(created_at) / 1000, tz=UTC)
                        pub_verified = True
                        pub_method = "unix_timestamp_ms"
                    except Exception:
                        pass

                # Location
                categories = posting.get("categories", {})
                location = categories.get("location", "")
                is_remote = "remote" in (location or "").lower() or "remote" in title.lower()
                team = categories.get("team", "")

                jobs.append({
                    "title": title,
                    "company": company_name,
                    "source_name": "Lever",
                    "source_url": job_url,
                    "url_hash": _url_hash(job_url),
                    "published_at": pub_dt,
                    "published_at_verified": pub_verified,
                    "published_at_method": pub_method,
                    "discovered_at": now,
                    "collected_at": now,
                    "is_remote": is_remote,
                    "role_family": classify_role_family(title),
                    "location": location,
                    "is_fresh": False,
                    "extra_data": {"team": team, "commitment": categories.get("commitment")},
                })

            logger.info(f"Lever {company_name}: {len(data)} jobs")
            await asyncio.sleep(0.5)

        return jobs

    # ─────────────────────────────────────────────────────────────────────
    # Source C: Y Combinator Work at a Startup
    # ─────────────────────────────────────────────────────────────────────
    async def _collect_yc_jobs(self) -> List[Dict[str, Any]]:
        """
        YC Work at a Startup public API.
        Source: https://www.workatastartup.com/jobs (JSON API)
        Rationale: Direct access to YC-backed AI startup jobs.
        """
        jobs: List[Dict[str, Any]] = []
        now = datetime.now(UTC)
        url = "https://www.workatastartup.com/jobs.json"
        params = {
            "companyBatch": "",
            "demographic": "",
            "disability": "",
            "inUSA": "",
            "query": "AI machine learning",
            "role": "",
            "remote": "",
            "visa": "",
        }
        data = await self.fetch(url, params=params)
        if not isinstance(data, dict):
            # Try alternate endpoint
            data = await self.fetch("https://www.workatastartup.com/jobs.json")

        if isinstance(data, dict):
            job_list = data.get("jobs", [])
            for job in job_list:
                title = job.get("title", "")
                if not title:
                    continue
                company_name = job.get("company", {}).get("name", "") if isinstance(job.get("company"), dict) else job.get("companyName", "")
                job_id = job.get("id", "")
                job_url = f"https://www.workatastartup.com/jobs/{job_id}"
                created_str = job.get("createdAt") or job.get("updated_at") or ""
                pub_dt: Optional[datetime] = None
                pub_verified = False
                pub_method = "not_found"
                if created_str:
                    pub_dt, pub_verified, pub_method = parse_date_string(str(created_str), now=now)

                is_remote = job.get("remote", False) or "remote" in title.lower()
                location = job.get("location") or job.get("locationName") or ""

                jobs.append({
                    "title": title,
                    "company": company_name,
                    "source_name": "Y Combinator Work at a Startup",
                    "source_url": job_url,
                    "url_hash": _url_hash(job_url),
                    "published_at": pub_dt,
                    "published_at_verified": pub_verified,
                    "published_at_method": pub_method,
                    "discovered_at": now,
                    "collected_at": now,
                    "is_remote": bool(is_remote),
                    "role_family": classify_role_family(title),
                    "location": location,
                    "is_fresh": False,
                    "extra_data": {"yc_batch": job.get("batch")},
                })

        logger.info(f"YC Jobs: {len(jobs)} jobs")
        return jobs

    # ─────────────────────────────────────────────────────────────────────
    # Source D: Ashby public job boards
    # ─────────────────────────────────────────────────────────────────────
    async def _collect_ashby(self) -> List[Dict[str, Any]]:
        """
        Ashby public job board API.
        Source: https://api.ashbyhq.com/posting-api/job-board/{company}
        """
        jobs: List[Dict[str, Any]] = []
        now = datetime.now(UTC)
        ASHBY_COMPANIES = [
            ("linear", "Linear"),
            ("vercel", "Vercel"),
            ("clerk", "Clerk"),
            ("descript", "Descript"),
            ("mem-labs", "Mem"),
            ("perplexity", "Perplexity AI"),
            ("cohere", "Cohere"),
            ("imbue", "Imbue"),
            ("typeface", "Typeface"),
            ("aisera", "AISera"),
        ]
        for slug, company_name in ASHBY_COMPANIES:
            url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
            data = await self.fetch(url)
            if not isinstance(data, dict):
                continue
            postings = data.get("jobPostings", [])
            for posting in postings:
                title = posting.get("title", "")
                if not title:
                    continue
                job_url = posting.get("jobUrl") or f"https://jobs.ashbyhq.com/{slug}/{posting.get('id', '')}"
                pub_dt = None
                pub_verified = False
                pub_method = "not_found"
                created = posting.get("publishedDate") or posting.get("createdAt")
                if created:
                    pub_dt, pub_verified, pub_method = parse_date_string(str(created), now=now)
                is_remote = posting.get("isRemote", False) or "remote" in title.lower()
                location = posting.get("locationName") or posting.get("location") or ""
                jobs.append({
                    "title": title,
                    "company": company_name,
                    "source_name": "Ashby",
                    "source_url": job_url,
                    "url_hash": _url_hash(job_url),
                    "published_at": pub_dt,
                    "published_at_verified": pub_verified,
                    "published_at_method": pub_method,
                    "discovered_at": now,
                    "collected_at": now,
                    "is_remote": bool(is_remote),
                    "role_family": classify_role_family(title),
                    "location": location,
                    "is_fresh": False,
                    "extra_data": {"department": posting.get("department")},
                })
            logger.info(f"Ashby {company_name}: {len(postings)} jobs")
            await asyncio.sleep(0.5)
        return jobs

    # ─────────────────────────────────────────────────────────────────────
    # Source E: Hacker News "Who is Hiring?" monthly thread
    # ─────────────────────────────────────────────────────────────────────
    async def _collect_hn_hiring(self) -> List[Dict[str, Any]]:
        """
        Hacker News 'Who is Hiring?' monthly thread via official HN Firebase API.
        Source: https://hacker-news.firebaseio.com/v0/
        Rationale: Tech community job board with AI job postings.
        """
        jobs: List[Dict[str, Any]] = []
        now = datetime.now(UTC)

        # Find the most recent "Ask HN: Who is hiring?" thread
        top_stories_url = "https://hacker-news.firebaseio.com/v0/askstories.json"
        story_ids = await self.fetch(top_stories_url)
        if not isinstance(story_ids, list):
            return jobs

        hiring_story_id = None
        for story_id in story_ids[:100]:
            story_url = f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
            story = await self.fetch(story_url)
            if isinstance(story, dict) and "who is hiring" in (story.get("title") or "").lower():
                hiring_story_id = story_id
                break

        if not hiring_story_id:
            logger.warning("HN: Could not find 'Who is Hiring?' thread")
            return jobs

        # Get the thread
        thread_url = f"https://hacker-news.firebaseio.com/v0/item/{hiring_story_id}.json"
        thread = await self.fetch(thread_url)
        if not isinstance(thread, dict):
            return jobs

        kids = thread.get("kids", [])[:100]  # First 100 comments
        ai_keywords = ["ai", "ml", "machine learning", "llm", "gpt", "neural", "nlp", "deep learning", "computer vision"]

        for kid_id in kids:
            comment_url = f"https://hacker-news.firebaseio.com/v0/item/{kid_id}.json"
            comment = await self.fetch(comment_url)
            if not isinstance(comment, dict):
                continue
            text = comment.get("text", "") or ""
            if not any(kw in text.lower() for kw in ai_keywords):
                continue

            # Extract first line as title
            from bs4 import BeautifulSoup
            clean_text = BeautifulSoup(text, "lxml").get_text(separator="\n")
            lines = [l.strip() for l in clean_text.split("\n") if l.strip()]
            title = lines[0][:200] if lines else f"HN Job #{kid_id}"
            source_url = f"https://news.ycombinator.com/item?id={kid_id}"
            created_at_ts = comment.get("time")
            pub_dt = None
            if created_at_ts:
                pub_dt = datetime.fromtimestamp(int(created_at_ts), tz=UTC)

            jobs.append({
                "title": title,
                "company": None,
                "source_name": "Hacker News Who is Hiring",
                "source_url": source_url,
                "url_hash": _url_hash(source_url),
                "published_at": pub_dt,
                "published_at_verified": True,
                "published_at_method": "hn_unix_timestamp",
                "discovered_at": now,
                "collected_at": now,
                "is_remote": "remote" in text.lower(),
                "role_family": classify_role_family(title),
                "location": None,
                "is_fresh": False,
                "extra_data": {"hn_story_id": hiring_story_id, "hn_comment_id": kid_id},
            })

        logger.info(f"HN Hiring: {len(jobs)} AI jobs")
        return jobs

    async def collect(self) -> List[Dict[str, Any]]:
        """Collect AI jobs from all five sources."""
        logger.info("Starting job collection from 5 sources...")

        gh_task = asyncio.create_task(self._collect_greenhouse())
        lv_task = asyncio.create_task(self._collect_lever())
        yc_task = asyncio.create_task(self._collect_yc_jobs())
        ashby_task = asyncio.create_task(self._collect_ashby())
        hn_task = asyncio.create_task(self._collect_hn_hiring())

        results = await asyncio.gather(
            gh_task, lv_task, yc_task, ashby_task, hn_task, return_exceptions=True
        )

        all_jobs: List[Dict[str, Any]] = []
        for result, name in zip(results, ["Greenhouse", "Lever", "YC Jobs", "Ashby", "HN Hiring"]):
            if isinstance(result, Exception):
                logger.error(f"Job source {name} failed", extra={"error": str(result)})
            else:
                all_jobs.extend(result)
                logger.info(f"{name}: {len(result)} jobs")

        self._metrics.records_discovered = len(all_jobs)
        logger.info(f"Total jobs collected: {len(all_jobs)}")
        return all_jobs
