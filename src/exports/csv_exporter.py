"""
CSV exporter: writes all entity types to data/exports/*.csv
"""
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


def _safe_str(val: Any) -> str:
    if val is None:
        return ""
    if isinstance(val, (list, dict)):
        import json
        return json.dumps(val, default=str)
    if isinstance(val, datetime):
        return val.isoformat()
    return str(val)


def _write_csv(path: Path, fieldnames: List[str], records: List[Dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for rec in records:
            row = {}
            for k in fieldnames:
                v = rec.get(k)
                if v is None and k == "product_name":
                    v = rec.get("entity_name")
                elif v is None and k == "company_name":
                    v = rec.get("startup_name")
                elif v is None and k == "startup_name":
                    v = rec.get("company_name") or rec.get("entity_name")
                row[k] = _safe_str(v)
            writer.writerow(row)
    return len(records)


STARTUP_FIELDS = [
    "startup_name", "entity_name", "canonical_name", "source_name", "source_url",
    "employee_count", "description", "collected_at",
]

PRODUCT_FIELDS = [
    "product_name", "company_name", "pricing_model", "source_name",
    "source_url", "description", "collected_at",
]

PAPER_FIELDS = [
    "title", "authors", "paper_url", "arxiv_id", "abstract",
    "github_url", "github_stars", "github_stars_collected_at",
    "published_date", "source_name", "collected_at",
]

JOB_FIELDS = [
    "title", "company", "canonical_company", "source_name", "source_url",
    "published_at", "published_at_verified", "is_remote", "role_family",
    "location", "is_fresh", "collected_at",
]

NEWS_FIELDS = [
    "title", "source_name", "source_url", "published_at",
    "published_at_verified", "published_at_method", "is_fresh",
    "full_text", "collected_at",
]


def export_all_csv(
    data: Dict[str, List[Dict[str, Any]]],
    exports_dir: Path,
) -> Dict[str, str]:
    paths: Dict[str, str] = {}

    if data.get("startups"):
        p = exports_dir / "startups.csv"
        _write_csv(p, STARTUP_FIELDS, data["startups"])
        paths["startups"] = str(p)

    if data.get("products"):
        p = exports_dir / "products.csv"
        _write_csv(p, PRODUCT_FIELDS, data["products"])
        paths["products"] = str(p)

    if data.get("research_papers"):
        p = exports_dir / "research_papers.csv"
        _write_csv(p, PAPER_FIELDS, data["research_papers"])
        paths["research_papers"] = str(p)

    if data.get("jobs"):
        p = exports_dir / "jobs.csv"
        _write_csv(p, JOB_FIELDS, data["jobs"])
        paths["jobs"] = str(p)

    if data.get("news"):
        p = exports_dir / "news.csv"
        _write_csv(p, NEWS_FIELDS, data["news"])
        paths["news"] = str(p)

    return paths
