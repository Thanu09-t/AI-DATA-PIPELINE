"""
Structured logging module with JSON output and rich console display.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


class JSONFormatter(logging.Formatter):
    """Structured JSON log formatter."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        # Attach any extra fields
        for key, val in record.__dict__.items():
            if key not in {
                "name", "msg", "args", "levelname", "levelno", "pathname",
                "filename", "module", "exc_info", "exc_text", "stack_info",
                "lineno", "funcName", "created", "msecs", "relativeCreated",
                "thread", "threadName", "processName", "process", "message",
                "taskName",
            }:
                log_obj[key] = val
        return json.dumps(log_obj, default=str)


class ConsoleFormatter(logging.Formatter):
    """Human-readable console formatter with colour codes."""

    COLORS = {
        "DEBUG": "\033[36m",    # Cyan
        "INFO": "\033[32m",     # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",    # Red
        "CRITICAL": "\033[35m", # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, "")
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        msg = record.getMessage()
        return f"{color}[{ts}] [{record.levelname:8s}] {record.name}: {msg}{self.RESET}"


def get_logger(name: str, log_dir: Optional[Path] = None, level: str = "INFO") -> logging.Logger:
    """Return a configured logger writing JSON to file and coloured output to console."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # Already configured

    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.propagate = False

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(ConsoleFormatter())
    logger.addHandler(ch)

    # File handler (JSON)
    if log_dir is None:
        log_dir = Path("data/logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(log_dir / f"{name.replace('.', '_')}.log", encoding="utf-8")
    fh.setFormatter(JSONFormatter())
    logger.addHandler(fh)

    return logger


# Platform root logger
def setup_root_logger(level: str = "INFO", log_dir: Optional[Path] = None) -> logging.Logger:
    return get_logger("ai_intel", log_dir=log_dir, level=level)
