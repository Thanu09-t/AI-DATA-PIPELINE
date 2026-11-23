"""
Data enrichment utilities: adds derived fields and cross-links entities.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from src.monitoring.logger import get_logger

logger = get_logger("processing.enrichment")

# Pattern to find GitHub URLs in text
_GH_URL_PATTERN = re.compile(
    r"https?://github\.com/([a-zA-Z0-9_\-\.]+)/([a-zA-Z0-9_\-\.]+)",
    re.I,
)


def extract_github_url(text: str) -> Optional[str]:
    """Extract the first valid GitHub repository URL from text."""
    if not text:
        return None
    m = _GH_URL_PATTERN.search(text)
    if m:
        # Normalize: remove trailing .git
        url = m.group(0).rstrip("/")
        if url.endswith(".git"):
            url = url[:-4]
        return url
    return None


def extract_arxiv_id(url: str) -> Optional[str]:
    """Extract arXiv paper ID from a URL or string."""
    patterns = [
        re.compile(r"arxiv\.org/abs/([0-9]+\.[0-9]+(?:v\d+)?)"),
        re.compile(r"arxiv\.org/pdf/([0-9]+\.[0-9]+(?:v\d+)?)"),
        re.compile(r"^([0-9]{4}\.[0-9]{4,5}(?:v\d+)?)$"),
    ]
    for pat in patterns:
        m = pat.search(url)
        if m:
            return m.group(1)
    return None


def enrich_startup(record: Dict[str, Any]) -> Dict[str, Any]:
    """Add derived fields to startup record."""
    # Normalize entity name whitespace
    name = record.get("entity_name", "")
    record["entity_name"] = " ".join(name.split())
    return record


def enrich_product(record: Dict[str, Any]) -> Dict[str, Any]:
    """Add derived fields to product record."""
    name = record.get("entity_name", "")
    record["entity_name"] = " ".join(name.split())
    return record


def enrich_paper(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Try to find a GitHub URL from the abstract or extra fields.
    Sets arxiv_id if derivable from paper_url.
    """
    paper_url = record.get("paper_url", "")
    if not record.get("arxiv_id"):
        record["arxiv_id"] = extract_arxiv_id(paper_url)

    # Try to find GitHub URL from abstract
    if not record.get("github_url"):
        abstract = record.get("abstract", "") or ""
        gh_url = extract_github_url(abstract)
        if gh_url:
            record["github_url"] = gh_url
            logger.debug(
                "GitHub URL extracted from abstract",
                extra={"arxiv_id": record.get("arxiv_id"), "github_url": gh_url},
            )
    return record
