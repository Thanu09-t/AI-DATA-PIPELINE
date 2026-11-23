"""
Platform metrics tracker: thread-safe, in-process counters.
For distributed metrics, push to Redis or Prometheus.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any


@dataclass
class PipelineMetrics:
    pipeline: str
    started_at: float = field(default_factory=time.monotonic)
    records_discovered: int = 0
    records_extracted: int = 0
    records_validated: int = 0
    records_rejected: int = 0
    duplicates_removed: int = 0
    llm_calls: int = 0
    llm_failures: int = 0
    provider_switches: int = 0
    rate_limit_events: int = 0
    retry_attempts: int = 0
    db_writes: int = 0
    errors: int = 0

    def elapsed(self) -> float:
        return time.monotonic() - self.started_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pipeline": self.pipeline,
            "elapsed_seconds": round(self.elapsed(), 2),
            "records_discovered": self.records_discovered,
            "records_extracted": self.records_extracted,
            "records_validated": self.records_validated,
            "records_rejected": self.records_rejected,
            "duplicates_removed": self.duplicates_removed,
            "llm_calls": self.llm_calls,
            "llm_failures": self.llm_failures,
            "provider_switches": self.provider_switches,
            "rate_limit_events": self.rate_limit_events,
            "retry_attempts": self.retry_attempts,
            "db_writes": self.db_writes,
            "errors": self.errors,
        }


class MetricsRegistry:
    """Global in-process registry of pipeline metrics."""

    _instance: "MetricsRegistry | None" = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._pipelines: Dict[str, PipelineMetrics] = {}
        self._lock = threading.Lock()
        self._start_time = datetime.now(timezone.utc)

    @classmethod
    def get(cls) -> "MetricsRegistry":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def pipeline(self, name: str) -> PipelineMetrics:
        with self._lock:
            if name not in self._pipelines:
                self._pipelines[name] = PipelineMetrics(pipeline=name)
            return self._pipelines[name]

    def summary(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "started_at": self._start_time.isoformat(),
                "pipelines": {k: v.to_dict() for k, v in self._pipelines.items()},
            }


# Singleton accessor
metrics = MetricsRegistry.get()
