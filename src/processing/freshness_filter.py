"""
Freshness filter: applies strict 24-hour window to news and job records.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from src.processing.date_normalizer import is_fresh, parse_date_string
from src.monitoring.logger import get_logger

logger = get_logger("processing.freshness_filter")

UTC = timezone.utc


def apply_freshness_filter(
    records: List[Dict[str, Any]],
    date_fields: List[str],
    freshness_hours: int = 24,
    now: Optional[datetime] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Classify records into fresh and stale buckets.

    Args:
        records: List of dicts with date information.
        date_fields: Ordered list of field names to try for the publication date.
        freshness_hours: Hours back from now to consider fresh.
        now: Reference time (defaults to UTC now).

    Returns:
        (fresh_records, stale_records)
    """
    if now is None:
        now = datetime.now(UTC)

    fresh: List[Dict[str, Any]] = []
    stale: List[Dict[str, Any]] = []

    for rec in records:
        pub_dt = None
        verified = False
        method = "not_checked"

        for field in date_fields:
            raw = rec.get(field)
            if raw:
                if isinstance(raw, datetime):
                    pub_dt = raw
                    verified = True
                    method = f"field_{field}_datetime"
                    break
                elif isinstance(raw, str):
                    dt, v, m = parse_date_string(raw, now=now)
                    if dt:
                        pub_dt = dt
                        verified = v
                        method = f"field_{field}_{m}"
                        break

        fresh_flag = is_fresh(pub_dt, freshness_hours=freshness_hours, now=now)

        # Annotate the record
        rec["_pub_dt"] = pub_dt.isoformat() if pub_dt else None
        rec["_pub_verified"] = verified
        rec["_pub_method"] = method
        rec["is_fresh"] = fresh_flag

        if fresh_flag:
            fresh.append(rec)
        else:
            stale.append(rec)

    logger.info(
        "Freshness filter applied",
        extra={
            "total": len(records),
            "fresh": len(fresh),
            "stale": len(stale),
            "freshness_hours": freshness_hours,
        },
    )
    return fresh, stale
