"""
Pydantic validators for all entity types.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from src.database.schemas import PricingModel
from src.monitoring.logger import get_logger

logger = get_logger("processing.validators")

VALID_PRICING_MODELS = {m.value for m in PricingModel}
VALID_ROLE_FAMILIES = {
    "Engineering", "Research", "Data Science", "Product", "Design",
    "Marketing", "Sales", "Operations", "Legal", "Finance", "HR", "Other",
}


def is_valid_url(url: Optional[str]) -> bool:
    if not url:
        return False
    try:
        p = urlparse(url)
        return p.scheme in ("http", "https") and bool(p.netloc)
    except Exception:
        return False


def validate_startup(record: Dict[str, Any]) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    if not record.get("entity_name"):
        errors.append("entity_name is required")
    if not is_valid_url(record.get("source_url")):
        errors.append(f"source_url is invalid: {record.get('source_url')}")
    if not record.get("source_name"):
        errors.append("source_name is required")
    ec = record.get("employee_count")
    if ec is not None and (not isinstance(ec, int) or ec < 0):
        errors.append(f"employee_count must be a non-negative integer: {ec}")
    return len(errors) == 0, errors


def validate_product(record: Dict[str, Any]) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    if not record.get("entity_name"):
        errors.append("entity_name is required")
    if not is_valid_url(record.get("source_url")):
        errors.append(f"source_url is invalid: {record.get('source_url')}")
    pm = record.get("pricing_model")
    if pm and pm not in VALID_PRICING_MODELS:
        errors.append(f"pricing_model '{pm}' is not a valid value")
    return len(errors) == 0, errors


def validate_paper(record: Dict[str, Any]) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    if not record.get("title"):
        errors.append("title is required")
    if not is_valid_url(record.get("paper_url")):
        errors.append(f"paper_url is invalid: {record.get('paper_url')}")
    gh_url = record.get("github_url")
    if gh_url and not is_valid_url(gh_url):
        errors.append(f"github_url is invalid: {gh_url}")
    stars = record.get("github_stars")
    if stars is not None and (not isinstance(stars, int) or stars < 0):
        errors.append("github_stars must be a non-negative integer")
    return len(errors) == 0, errors


def validate_news(record: Dict[str, Any]) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    if not record.get("title"):
        errors.append("title is required")
    if not is_valid_url(record.get("source_url")):
        errors.append(f"source_url is invalid: {record.get('source_url')}")
    return len(errors) == 0, errors


def validate_job(record: Dict[str, Any]) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    if not record.get("title"):
        errors.append("title is required")
    if not is_valid_url(record.get("source_url")):
        errors.append(f"source_url is invalid: {record.get('source_url')}")
    rf = record.get("role_family")
    if rf and rf not in VALID_ROLE_FAMILIES:
        # Not a hard error, just a warning
        logger.debug("Unknown role_family", extra={"role_family": rf})
    return len(errors) == 0, errors


def classify_role_family(title: str) -> str:
    """Heuristically classify job title into a role family."""
    title_lower = title.lower()
    if any(w in title_lower for w in ["engineer", "developer", "swe", "software", "backend", "frontend", "fullstack", "devops", "platform", "infrastructure", "ml engineer"]):
        return "Engineering"
    if any(w in title_lower for w in ["research", "scientist", "phd", "researcher"]):
        return "Research"
    if any(w in title_lower for w in ["data", "analyst", "analytics", "bi "]):
        return "Data Science"
    if any(w in title_lower for w in ["product manager", "pm ", " pm", "product owner"]):
        return "Product"
    if any(w in title_lower for w in ["design", "ux", "ui "]):
        return "Design"
    if any(w in title_lower for w in ["market", "growth", "seo", "content"]):
        return "Marketing"
    if any(w in title_lower for w in ["sales", "account exec", "account manager", "business development"]):
        return "Sales"
    if any(w in title_lower for w in ["legal", "counsel", "compliance"]):
        return "Legal"
    if any(w in title_lower for w in ["finance", "accounting", "cfo", "controller"]):
        return "Finance"
    if any(w in title_lower for w in ["hr", "recruiter", "people ops", "talent"]):
        return "HR"
    return "Other"
