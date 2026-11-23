"""
Mapping logger: exports entity resolution decisions to CSV and DB.
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from src.monitoring.logger import get_logger

logger = get_logger("resolution.mapping_logger")


def export_mapping_log(
    entries: List[Dict[str, Any]],
    output_path: Path,
) -> int:
    """Write entity mapping log to CSV. Returns rows written."""
    if not entries:
        logger.warning("No mapping log entries to export")
        return 0

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "raw_name", "canonical_name", "normalized_name",
        "matching_method", "confidence_score", "source_url",
        "record_type", "resolved_at", "requires_review", "notes",
    ]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(entries)

    logger.info(f"Mapping log exported: {len(entries)} entries → {output_path}")
    return len(entries)
