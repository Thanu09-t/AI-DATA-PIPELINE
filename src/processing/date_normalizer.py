"""
Date normalization engine: handles all common date formats found in news/job sources.
Always returns timezone-aware UTC datetimes.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

import pytz
from dateutil import parser as dateutil_parser

from src.monitoring.logger import get_logger

logger = get_logger("processing.date_normalizer")

UTC = timezone.utc

# Relative date patterns
_RELATIVE_PATTERNS = [
    (re.compile(r"(\d+)\s*second[s]?\s*ago", re.I), "seconds"),
    (re.compile(r"(\d+)\s*minute[s]?\s*ago", re.I), "minutes"),
    (re.compile(r"(\d+)\s*hour[s]?\s*ago", re.I), "hours"),
    (re.compile(r"(\d+)\s*day[s]?\s*ago", re.I), "days"),
    (re.compile(r"(\d+)\s*week[s]?\s*ago", re.I), "weeks"),
    (re.compile(r"just\s+now", re.I), "just_now"),
    (re.compile(r"today", re.I), "today"),
    (re.compile(r"yesterday", re.I), "yesterday"),
]


def parse_relative(text: str, now: Optional[datetime] = None) -> Optional[datetime]:
    """Parse relative date strings like '2 hours ago', 'yesterday'."""
    if now is None:
        now = datetime.now(UTC)
    for pattern, unit in _RELATIVE_PATTERNS:
        m = pattern.search(text)
        if m:
            if unit == "just_now":
                return now
            if unit == "today":
                return now.replace(hour=12, minute=0, second=0, microsecond=0)
            if unit == "yesterday":
                return (now - timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0)
            n = int(m.group(1))
            delta_kwargs = {unit: n}
            return now - timedelta(**delta_kwargs)
    return None


def normalize_to_utc(dt: datetime) -> datetime:
    """Ensure datetime is UTC-aware."""
    if dt.tzinfo is None:
        # Assume UTC if no timezone
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def parse_date_string(
    text: str, now: Optional[datetime] = None
) -> Tuple[Optional[datetime], bool, str]:
    """
    Parse a date string into a UTC datetime.

    Returns:
        (datetime_utc, is_verified, method_description)
        is_verified = True when date is explicitly stated (not inferred).
    """
    if not text or not text.strip():
        return None, False, "missing"

    text = text.strip()

    # 1. Try relative dates first
    relative = parse_relative(text, now)
    if relative:
        return normalize_to_utc(relative), True, "relative_date"

    # 2. Try ISO-8601 / RFC patterns with dateutil
    try:
        dt = dateutil_parser.parse(text, fuzzy=False)
        return normalize_to_utc(dt), True, "parsed_explicit"
    except (ValueError, OverflowError):
        pass

    # 3. Try fuzzy parsing as last resort
    try:
        dt = dateutil_parser.parse(text, fuzzy=True)
        return normalize_to_utc(dt), False, "fuzzy_parse"
    except Exception:
        pass

    logger.debug("Failed to parse date string", extra={"text": text})
    return None, False, "parse_failed"


def is_fresh(
    dt: Optional[datetime],
    freshness_hours: int = 24,
    now: Optional[datetime] = None,
) -> bool:
    """Return True if dt falls within freshness_hours before now (UTC)."""
    if dt is None:
        return False
    if now is None:
        now = datetime.now(UTC)
    dt_utc = normalize_to_utc(dt)
    cutoff = now - timedelta(hours=freshness_hours)
    return cutoff <= dt_utc <= now


def extract_date_from_html_meta(html: str) -> Tuple[Optional[datetime], bool, str]:
    """
    Extract publication date from HTML meta tags, JSON-LD, or time elements.
    Returns (datetime, verified, method).
    """
    import json
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")

    # 1. JSON-LD
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            if isinstance(data, list):
                data = data[0] if data else {}
            for key in ["datePublished", "dateModified", "dateCreated"]:
                val = data.get(key)
                if val:
                    dt, verified, method = parse_date_string(val)
                    if dt:
                        return dt, True, f"json_ld_{key}"
        except Exception:
            pass

    # 2. OpenGraph
    og = soup.find("meta", property="article:published_time")
    if og and og.get("content"):
        dt, verified, method = parse_date_string(og["content"])
        if dt:
            return dt, True, "og_published_time"

    # 3. HTML <time> element
    time_el = soup.find("time")
    if time_el:
        dt_attr = time_el.get("datetime", "")
        if dt_attr:
            dt, verified, method = parse_date_string(dt_attr)
            if dt:
                return dt, True, "html_time_element"
        # Try inner text
        inner = time_el.get_text(strip=True)
        if inner:
            dt, verified, method = parse_date_string(inner)
            if dt:
                return dt, False, "html_time_text"

    # 4. Various meta tags
    meta_names = [
        "pubdate", "publishdate", "date", "article:published_time",
        "og:published_time", "DC.date", "last-modified",
    ]
    for name in meta_names:
        tag = soup.find("meta", attrs={"name": name}) or soup.find(
            "meta", attrs={"property": name}
        )
        if tag and tag.get("content"):
            dt, verified, method = parse_date_string(tag["content"])
            if dt:
                return dt, True, f"meta_{name}"

    return None, False, "not_found_in_html"
