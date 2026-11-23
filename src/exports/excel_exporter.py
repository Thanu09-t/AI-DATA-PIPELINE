"""
Excel exporter: creates a multi-sheet workbook: ai_intelligence_output.xlsx
Sheets: Startups, Products, Research Papers, Jobs, News, Entity Mapping Log
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

from src.exports.csv_exporter import (
    STARTUP_FIELDS, PRODUCT_FIELDS, PAPER_FIELDS, JOB_FIELDS, NEWS_FIELDS
)
from src.monitoring.logger import get_logger

logger = get_logger("exports.excel")

MAPPING_FIELDS = [
    "raw_name", "canonical_name", "normalized_name", "matching_method",
    "confidence_score", "source_url", "record_type", "resolved_at",
    "requires_review", "notes",
]

HEADER_FILL = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
HEADER_FONT = Font(bold=True, color="FFFFFF", size=11)


def _safe_cell_value(val: Any) -> Any:
    if val is None:
        return ""
    if isinstance(val, (list, dict)):
        import json
        return json.dumps(val, default=str)
    if isinstance(val, datetime):
        return val.isoformat()
    if isinstance(val, bool):
        return "Yes" if val else "No"
    return val


def _write_sheet(
    wb: openpyxl.Workbook,
    sheet_name: str,
    fieldnames: List[str],
    records: List[Dict[str, Any]],
) -> None:
    ws = wb.create_sheet(title=sheet_name)

    # Header row
    for col_idx, field in enumerate(fieldnames, start=1):
        cell = ws.cell(row=1, column=col_idx, value=field.replace("_", " ").title())
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center")

    # Data rows
    for row_idx, rec in enumerate(records, start=2):
        for col_idx, field in enumerate(fieldnames, start=1):
            val = rec.get(field)
            if val is None and field == "product_name":
                val = rec.get("entity_name")
            elif val is None and field == "company_name":
                val = rec.get("startup_name")
            elif val is None and field == "startup_name":
                val = rec.get("company_name") or rec.get("entity_name")
            ws.cell(row=row_idx, column=col_idx, value=_safe_cell_value(val))

    # Auto-width
    for col_idx, field in enumerate(fieldnames, start=1):
        col_letter = get_column_letter(col_idx)
        max_len = max(len(field), 10)
        ws.column_dimensions[col_letter].width = min(max_len + 4, 50)

    # Freeze header
    ws.freeze_panes = "A2"


def export_excel(
    data: Dict[str, List[Dict[str, Any]]],
    output_path: Path,
    mapping_log: List[Dict[str, Any]],
) -> str:
    wb = openpyxl.Workbook()
    # Remove default sheet
    wb.remove(wb.active)

    # Summary sheet
    ws_summary = wb.create_sheet(title="Summary", index=0)
    ws_summary["A1"] = "AI Intelligence Ingestion Platform"
    ws_summary["A1"].font = Font(bold=True, size=16)
    ws_summary["A3"] = f"Generated: {datetime.now().isoformat()}"
    summary_data = [
        ("Startups", len(data.get("startups", []))),
        ("Products", len(data.get("products", []))),
        ("Research Papers", len(data.get("research_papers", []))),
        ("Jobs", len(data.get("jobs", []))),
        ("News Articles", len(data.get("news", []))),
        ("Entity Mappings", len(mapping_log)),
    ]
    for i, (name, count) in enumerate(summary_data, start=5):
        ws_summary[f"A{i}"] = name
        ws_summary[f"B{i}"] = count

    _write_sheet(wb, "Startups", STARTUP_FIELDS, data.get("startups", []))
    _write_sheet(wb, "Products", PRODUCT_FIELDS, data.get("products", []))
    _write_sheet(wb, "Research Papers", PAPER_FIELDS, data.get("research_papers", []))
    _write_sheet(wb, "Jobs", JOB_FIELDS, data.get("jobs", []))
    _write_sheet(wb, "News", NEWS_FIELDS, data.get("news", []))
    _write_sheet(wb, "Entity Mapping Log", MAPPING_FIELDS, mapping_log)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    logger.info(f"Excel workbook saved: {output_path} ({len(wb.sheetnames)} sheets)")
    return str(output_path)
