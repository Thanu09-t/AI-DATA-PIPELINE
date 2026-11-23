"""
JSON exporter: writes canonical JSON schemas to data/exports/*.json
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


def _serialize(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def export_all_json(
    data: Dict[str, List[Dict[str, Any]]],
    exports_dir: Path,
) -> Dict[str, str]:
    exports_dir.mkdir(parents=True, exist_ok=True)
    paths: Dict[str, str] = {}

    for key, records in data.items():
        if records:
            p = exports_dir / f"{key}.json"
            with open(p, "w", encoding="utf-8") as f:
                json.dump(records, f, default=_serialize, indent=2, ensure_ascii=False)
            paths[key] = str(p)

    return paths
