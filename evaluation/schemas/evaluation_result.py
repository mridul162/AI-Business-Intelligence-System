"""
evaluation/schemas/evaluation_result.py

Structured contract for the output of running one EvaluationCase against
the live pipeline, and for aggregating many such results into a report.

Design goal (per Phase 10.2/10.3): the result of a run must be able to
answer "the system failed *because* the LLM mapped 'total expenses' to
'orders' during NL parsing" -- not just "the system failed". That means
every result carries:

    - which pipeline stage the run actually stopped at (if any)
    - a field-by-field diff between expected and actual structured output
    - whether that matches where the case *expected* to fail (for
      intentionally-invalid cases)

This module has no dependency on any particular pipeline implementation --
see evaluation/runners/evaluation_runner.py for the piece that adapts a
real `AnalyticalQueryService` (or a mock) into this schema.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from evaluation.schemas.evaluation_case import (
    EvalCategory,
    Difficulty,
    ExpectedStatus,
    FailureStage,
)


# --------------------------------------------------------------------------- #
# Field-level diagnostics
# --------------------------------------------------------------------------- #

@dataclass
class FieldDiff:
    """One mismatched field between expected and actual structured output."""

    field: str          # "metrics" | "dimensions" | "filters" | "time_grain" | "time_range"
    expected: Any
    actual: Any

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# --------------------------------------------------------------------------- #
# Per-case result
# --------------------------------------------------------------------------- #

@dataclass
class EvaluationResult:
    case_id: str
    question: str
    category: str          # EvalCategory value, kept as str for easy JSON round-trip
    difficulty: str        # Difficulty value

    expected_status: str   # ExpectedStatus value: what the case declared
    actual_status: str     # "success" | "failure": what the pipeline actually did

    passed: bool

    # Where the pipeline actually stopped/failed. None if it ran to
    # completion (regardless of whether the result was correct).
    actual_failed_stage: Optional[str] = None

    # Where the case expected to fail (FAILURE cases only).
    expected_failed_stage: Optional[str] = None

    # Populated when actual_status == "success" but the structured output
    # didn't match `expected` -- this is the "ran fine but got the wrong
    # answer" bucket, distinct from a hard pipeline failure.
    field_diffs: List[FieldDiff] = field(default_factory=list)

    # Raw error/exception message, if the pipeline raised or returned an
    # explicit error.
    error: Optional[str] = None

    # Free-text explanation of *why* this result passed/failed, for humans
    # scanning a report -- e.g. "metrics mismatch: expected ['total_expenses'],
    # got ['orders']" or "expected failure at semantic_resolution, but
    # pipeline succeeded".
    reason: Optional[str] = None

    latency_ms: Optional[float] = None
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["field_diffs"] = [fd.to_dict() if isinstance(fd, FieldDiff) else fd for fd in self.field_diffs]
        return d


# --------------------------------------------------------------------------- #
# Aggregate breakdowns
# --------------------------------------------------------------------------- #

@dataclass
class GroupBreakdown:
    """Pass/fail counts for one group (a category, a difficulty level, etc.)."""

    group: str
    total: int
    passed: int
    failed: int

    @property
    def pass_rate(self) -> float:
        return round(100.0 * self.passed / self.total, 1) if self.total else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "group": self.group,
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "pass_rate": self.pass_rate,
        }


@dataclass
class FailureStageCount:
    stage: str
    count: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# --------------------------------------------------------------------------- #
# Full report
# --------------------------------------------------------------------------- #

@dataclass
class EvaluationReport:
    dataset_version: str
    run_timestamp: str
    total_cases: int
    passed: int
    failed: int

    by_category: List[GroupBreakdown] = field(default_factory=list)
    by_difficulty: List[GroupBreakdown] = field(default_factory=list)
    failure_stages: List[FailureStageCount] = field(default_factory=list)

    results: List[EvaluationResult] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        return round(100.0 * self.passed / self.total_cases, 1) if self.total_cases else 0.0

    def to_dict(self, include_results: bool = True) -> Dict[str, Any]:
        d = {
            "dataset_version": self.dataset_version,
            "run_timestamp": self.run_timestamp,
            "total_cases": self.total_cases,
            "passed": self.passed,
            "failed": self.failed,
            "pass_rate": self.pass_rate,
            "by_category": [b.to_dict() for b in self.by_category],
            "by_difficulty": [b.to_dict() for b in self.by_difficulty],
            "failure_stages": [f.to_dict() for f in self.failure_stages],
        }
        if include_results:
            d["results"] = [r.to_dict() for r in self.results]
        return d

    def save(self, path: str | Path, include_results: bool = True) -> None:
        Path(path).write_text(json.dumps(self.to_dict(include_results=include_results), indent=2))

    def print_summary(self) -> None:
        print(f"Evaluation run — dataset {self.dataset_version} @ {self.run_timestamp}")
        print(f"Total cases:      {self.total_cases}")
        print(f"Passed:           {self.passed}")
        print(f"Failed:           {self.failed}")
        print(f"Success rate:     {self.pass_rate}%")
        print()
        print("By category:")
        for b in self.by_category:
            print(f"  {b.group:<20} {b.pass_rate:>6.1f}%  ({b.passed}/{b.total})")
        print()
        print("By difficulty:")
        for b in self.by_difficulty:
            print(f"  {b.group:<20} {b.pass_rate:>6.1f}%  ({b.passed}/{b.total})")
        print()
        print("Failure stages:")
        if not self.failure_stages:
            print("  (none)")
        for f in self.failure_stages:
            print(f"  {f.stage:<20} {f.count}")

    @staticmethod
    def now_timestamp() -> str:
        return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------- #
# Report construction from a flat list of results
# --------------------------------------------------------------------------- #

def build_report(
    results: List[EvaluationResult],
    dataset_version: str = "v1",
) -> EvaluationReport:
    """Aggregate a flat list of EvaluationResult into an EvaluationReport."""

    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed

    by_category = _group_breakdown(results, key=lambda r: r.category)
    by_difficulty = _group_breakdown(results, key=lambda r: r.difficulty)

    stage_counts: Dict[str, int] = {}
    for r in results:
        if not r.passed and r.actual_failed_stage:
            stage_counts[r.actual_failed_stage] = stage_counts.get(r.actual_failed_stage, 0) + 1
    failure_stages = [
        FailureStageCount(stage=s, count=c)
        for s, c in sorted(stage_counts.items(), key=lambda kv: -kv[1])
    ]

    return EvaluationReport(
        dataset_version=dataset_version,
        run_timestamp=EvaluationReport.now_timestamp(),
        total_cases=total,
        passed=passed,
        failed=failed,
        by_category=by_category,
        by_difficulty=by_difficulty,
        failure_stages=failure_stages,
        results=results,
    )


def _group_breakdown(results: List[EvaluationResult], key) -> List[GroupBreakdown]:
    groups: Dict[str, List[EvaluationResult]] = {}
    for r in results:
        groups.setdefault(key(r), []).append(r)
    breakdowns = []
    for group_name, group_results in sorted(groups.items()):
        p = sum(1 for r in group_results if r.passed)
        breakdowns.append(GroupBreakdown(
            group=group_name,
            total=len(group_results),
            passed=p,
            failed=len(group_results) - p,
        ))
    return breakdowns