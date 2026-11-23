"""
Google Sheets exporter: uploads all six tabs to a Google Spreadsheet.
Uses service account authentication via GOOGLE_SHEETS_CREDENTIALS env var.

If credentials are not configured, this module explains how to enable the integration.
"""
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.monitoring.logger import get_logger

logger = get_logger("exports.google_sheets")

SHEET_TABS = [
    ("Startups", "startups"),
    ("Products", "products"),
    ("Research Papers", "research_papers"),
    ("Jobs", "jobs"),
    ("News", "news"),
]

MAPPING_TAB = "Entity Mapping Log"

MAX_CELLS_PER_REQUEST = 50000  # Stay within Sheets API limits
BATCH_SIZE = 500  # Rows per batch write


def _safe_value(val: Any) -> str:
    if val is None:
        return ""
    if isinstance(val, (list, dict)):
        return json.dumps(val, default=str)
    if isinstance(val, datetime):
        return val.isoformat()
    if isinstance(val, bool):
        return "Yes" if val else "No"
    return str(val)


def _get_fieldnames(entity_type: str) -> List[str]:
    from src.exports.csv_exporter import (
        STARTUP_FIELDS, PRODUCT_FIELDS, PAPER_FIELDS, JOB_FIELDS, NEWS_FIELDS
    )
    mapping = {
        "startups": STARTUP_FIELDS,
        "products": PRODUCT_FIELDS,
        "research_papers": PAPER_FIELDS,
        "jobs": JOB_FIELDS,
        "news": NEWS_FIELDS,
    }
    return mapping.get(entity_type, [])


def export_to_google_sheets(
    data: Dict[str, List[Dict[str, Any]]],
    mapping_log: List[Dict[str, Any]],
    settings: Any,
) -> Optional[str]:
    """
    Upload all data to Google Sheets.
    Returns the spreadsheet URL or None on failure.

    Authentication:
    - Set GOOGLE_SHEETS_CREDENTIALS to path of service account JSON file
    - Grant the service account edit access to the spreadsheet (or create new)
    """
    creds_path = settings.google_sheets_credentials
    if not creds_path:
        logger.warning(
            "Google Sheets integration disabled: GOOGLE_SHEETS_CREDENTIALS not set.\n"
            "To enable:\n"
            "1. Create a Google Cloud project\n"
            "2. Enable Sheets API and Drive API\n"
            "3. Create a service account and download JSON credentials\n"
            "4. Set GOOGLE_SHEETS_CREDENTIALS=path/to/credentials.json\n"
            "5. Share the target spreadsheet with the service account email"
        )
        return None

    creds_file = Path(creds_path)
    if not creds_file.exists():
        logger.error(f"Google credentials file not found: {creds_path}")
        return None

    try:
        import gspread
        from google.oauth2.service_account import Credentials

        SCOPES = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_file(str(creds_file), scopes=SCOPES)
        gc = gspread.authorize(creds)

        # Create or open spreadsheet
        spreadsheet_id = settings.google_spreadsheet_id
        if spreadsheet_id:
            sh = gc.open_by_key(spreadsheet_id)
            logger.info(f"Opened existing spreadsheet: {spreadsheet_id}")
        else:
            sh = gc.create("AI Intelligence Data: FrontierAtlas")
            sh.share(None, perm_type="anyone", role="reader")
            logger.info(f"Created new spreadsheet: {sh.id}")

        # Upload each tab
        for tab_name, data_key in SHEET_TABS:
            records = data.get(data_key, [])
            if not records:
                logger.info(f"No records for {tab_name}, skipping")
                continue

            fieldnames = _get_fieldnames(data_key)
            _upload_tab(sh, tab_name, fieldnames, records)
            logger.info(f"Uploaded {len(records)} rows to {tab_name}")

        # Entity Mapping Log
        if mapping_log:
            mapping_fields = [
                "raw_name", "canonical_name", "normalized_name", "matching_method",
                "confidence_score", "source_url", "record_type", "resolved_at",
                "requires_review", "notes",
            ]
            _upload_tab(sh, MAPPING_TAB, mapping_fields, mapping_log)
            logger.info(f"Uploaded {len(mapping_log)} rows to Entity Mapping Log")

        url = sh.url
        logger.info(f"Google Sheets export complete: {url}")
        return url

    except ImportError:
        logger.error("gspread not installed: pip install gspread google-auth")
        return None
    except Exception as exc:
        logger.error("Google Sheets export failed", extra={"error": str(exc)})
        return None


def _upload_tab(
    sh: Any,
    tab_name: str,
    fieldnames: List[str],
    records: List[Dict[str, Any]],
) -> None:
    """Create or clear a worksheet and upload records in batches."""
    # Get or create worksheet
    try:
        ws = sh.worksheet(tab_name)
        ws.clear()
    except Exception:
        ws = sh.add_worksheet(title=tab_name, rows=len(records) + 10, cols=len(fieldnames) + 2)

    # Build rows
    header = [f.replace("_", " ").title() for f in fieldnames]
    all_rows = [header]
    for rec in records:
        all_rows.append([_safe_value(rec.get(f)) for f in fieldnames])

    # Batch write
    for i in range(0, len(all_rows), BATCH_SIZE):
        batch = all_rows[i:i + BATCH_SIZE]
        start_row = i + 1
        ws.update(f"A{start_row}", batch)
        logger.debug(f"Uploaded rows {start_row}–{start_row + len(batch) - 1} to {tab_name}")
        time.sleep(1.0)  # Respect Sheets API rate limit
