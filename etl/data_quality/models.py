from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

VALID_STATUSES = {"PASS", "WARNING", "FAIL"}
VALID_SEVERITIES = {"INFO", "WARNING", "ERROR", "CRITICAL"}


@dataclass
class DataQualityResult:
    """Result for one data-quality check."""

    check_name: str
    status: str = "PASS"
    severity: str = "INFO"
    affected_rows: int = 0
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.status = self.status.upper()
        self.severity = self.severity.upper()

        if self.status not in VALID_STATUSES:
            raise ValueError(f"Unsupported status: {self.status}")

        if self.severity not in VALID_SEVERITIES:
            raise ValueError(f"Unsupported severity: {self.severity}")


@dataclass
class DataQualityCheck:
    """Registered routine used to run one data-quality check."""

    name: str
    func: Callable[[Any], DataQualityResult]


@dataclass
class DataQualityReport:
    """Aggregate report for a data-quality run."""

    checks: list[DataQualityResult]
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def status(self) -> str:
        if any(result.status == "FAIL" for result in self.checks):
            return "FAIL"
        if any(result.status == "WARNING" for result in self.checks):
            return "WARNING"
        return "PASS"

    @property
    def summary(self) -> dict[str, int]:
        summary = {
            "total_count": len(self.checks),
            "pass_count": 0,
            "warning_count": 0,
            "fail_count": 0,
        }

        for result in self.checks:
            if result.status == "PASS":
                summary["pass_count"] += 1
            elif result.status == "WARNING":
                summary["warning_count"] += 1
            elif result.status == "FAIL":
                summary["fail_count"] += 1

        return summary
