"""
Deduplication utilities: URL-hash-based and fuzzy-name-based deduplication.
"""
from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional, Set, Tuple

from rapidfuzz import fuzz, process

from src.monitoring.logger import get_logger

logger = get_logger("processing.deduplicator")


def url_hash(url: str) -> str:
    return hashlib.sha256(url.strip().lower().encode()).hexdigest()


def deduplicate_by_url(
    records: List[Dict[str, Any]], url_field: str = "source_url"
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Remove records with duplicate URLs.
    Returns (deduplicated_list, duplicate_count).
    """
    seen: Set[str] = set()
    deduped: List[Dict[str, Any]] = []
    duplicates = 0
    for rec in records:
        u = rec.get(url_field, "")
        h = url_hash(u)
        if h in seen:
            duplicates += 1
        else:
            seen.add(h)
            deduped.append(rec)
    return deduped, duplicates


def deduplicate_by_name(
    records: List[Dict[str, Any]],
    name_field: str = "entity_name",
    threshold: int = 95,
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Remove near-duplicate records based on name similarity.
    Uses RapidFuzz token_sort_ratio. Keeps first occurrence.
    """
    seen_names: List[str] = []
    deduped: List[Dict[str, Any]] = []
    duplicates = 0

    for rec in records:
        name = rec.get(name_field, "")
        if not name:
            deduped.append(rec)
            continue

        if not seen_names:
            seen_names.append(name)
            deduped.append(rec)
            continue

        match = process.extractOne(
            name,
            seen_names,
            scorer=fuzz.token_sort_ratio,
            score_cutoff=threshold,
        )
        if match:
            duplicates += 1
            logger.debug(
                "Duplicate by name",
                extra={"name": name, "matched": match[0], "score": match[1]},
            )
        else:
            seen_names.append(name)
            deduped.append(rec)

    return deduped, duplicates


def deduplicate_pipeline(
    records: List[Dict[str, Any]],
    url_field: str = "source_url",
    name_field: str = "entity_name",
    name_threshold: int = 95,
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """
    Full deduplication pipeline: URL-based then name-based.
    Returns (final_records, stats_dict).
    """
    original_count = len(records)
    after_url, url_dups = deduplicate_by_url(records, url_field)
    after_name, name_dups = deduplicate_by_name(after_url, name_field, name_threshold)
    stats = {
        "original": original_count,
        "after_url_dedup": len(after_url),
        "after_name_dedup": len(after_name),
        "url_duplicates": url_dups,
        "name_duplicates": name_dups,
        "total_removed": url_dups + name_dups,
    }
    logger.info("Deduplication complete", extra=stats)
    return after_name, stats
