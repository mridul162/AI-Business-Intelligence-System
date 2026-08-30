"""
evaluation/schemas/evaluation_case.py

Structured schema for evaluation cases used across the AI Business
Intelligence System's evaluation harness (Phase 10).

This schema is deliberately deterministic: every "expected" field is a
structured value (metric names, canonical time labels, filter tuples) that
can be compared directly against the pipeline's actual output with a plain
equality check, rather than requiring an LLM judge.

Pipeline stages this schema is designed to evaluate against:

    Natural Language Question
            |
            v
    NL Query Parser / LLM        -> ParsedQuery
            |
            v
    Semantic Resolution          -> resolved query objects
            |
            v
    QueryRequest
            |
            v
    Query Builder + Validation   -> Compiled SQL
            |
            v
    Execution                    -> AnalyticalQueryResponse
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


# --------------------------------------------------------------------------- #
# Enumerations
# --------------------------------------------------------------------------- #

class EvalCategory(str, Enum):
    """Matches the seven case categories described in Phase 10.1."""

    DIRECT_METRIC = "direct_metric"
    METRIC_PARAPHRASE = "metric_paraphrase"
    TIME_BASED = "time_based"
    DIMENSION = "dimension"
    FILTER = "filter"
    MULTI_METRIC = "multi_metric"
    AMBIGUOUS_INVALID = "ambiguous_invalid"
    NEW_METRIC_COVERAGE = "new_metric_coverage"



class Difficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class ExpectedStatus(str, Enum):
    """Whether the case is expected to succeed or to fail correctly."""

    SUCCESS = "success"
    FAILURE = "failure"


class FailureStage(str, Enum):
    """
    Where a case is expected to fail, for cases with expected_status =
    FAILURE. Also used post-hoc by the runner to classify unexpected
    failures on SUCCESS cases (see Phase 10.4 failure taxonomy).
    """

    PARSER = "parser"
    SEMANTIC_RESOLUTION = "semantic_resolution"
    TIME_RESOLUTION = "time_resolution"
    VALIDATION = "validation"
    SQL_COMPILATION = "sql_compilation"
    EXECUTION = "execution"
    NONE = "none"


# --------------------------------------------------------------------------- #
# Structured sub-objects
# --------------------------------------------------------------------------- #

@dataclass
class ExpectedFilter:
    """One expected filter clause, e.g. {"field": "payment_method",
    "operator": "=", "value": "cash"}"""

    field: str
    operator: str  # one of "=", "!=", ">", ">=", "<", "<="
    value: Any


@dataclass
class ExpectedOutput:
    """
    The structured, expected result of running the full pipeline (or an
    individual stage) on `question`. Every field defaults to an "empty"
    value so partial cases (e.g. parser-only fixtures) stay valid.

    time_grain:
        Canonical aggregation grain, e.g. "daily", "weekly", "monthly",
        "quarterly", "yearly", or None if no grouping was requested.
    time_range:
        Canonical resolved time window label, e.g. "today", "yesterday",
        "this_week", "last_month", "this_quarter", "this_year", or None
        if the question specified no time window at all. None is a
        meaningful, distinct value from an empty object -- this directly
        targets the "no time specified -> LLM returns empty TimeRange {}"
        regression.
    """

    metrics: List[str] = field(default_factory=list)
    dimensions: List[str] = field(default_factory=list)
    filters: List[ExpectedFilter] = field(default_factory=list)
    time_grain: Optional[str] = None
    time_range: Optional[str] = None


# --------------------------------------------------------------------------- #
# Top-level evaluation case
# --------------------------------------------------------------------------- #

from pydantic import BaseModel

class EvaluationCase(BaseModel):
    id: str
    question: str
    category: EvalCategory
    difficulty: Difficulty
    expected_status: ExpectedStatus

    expected: ExpectedOutput | None = None
    expected_failed_stage: FailureStage | None = None
    failure_reason: str | None = None
    notes: str | None = None

    def __post_init__(self) -> None:
        if self.expected_status == ExpectedStatus.SUCCESS and self.expected is None:
            raise ValueError(f"{self.id}: SUCCESS cases require `expected`")
        if self.expected_status == ExpectedStatus.FAILURE and self.expected_failed_stage is None:
            raise ValueError(f"{self.id}: FAILURE cases require `expected_failed_stage`")

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["category"] = self.category.value
        d["difficulty"] = self.difficulty.value
        d["expected_status"] = self.expected_status.value
        if self.expected_failed_stage is not None:
            d["expected_failed_stage"] = self.expected_failed_stage.value
        return d

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "EvaluationCase":
        expected = None
        if d.get("expected") is not None:
            raw = d["expected"]
            expected = ExpectedOutput(
                metrics=raw.get("metrics", []),
                dimensions=raw.get("dimensions", []),
                filters=[ExpectedFilter(**f) for f in raw.get("filters", [])],
                time_grain=raw.get("time_grain"),
                time_range=raw.get("time_range"),
            )
        return EvaluationCase(
            id=d["id"],
            question=d["question"],
            category=EvalCategory(d["category"]),
            difficulty=Difficulty(d["difficulty"]),
            expected_status=ExpectedStatus(d["expected_status"]),
            expected=expected,
            expected_failed_stage=(
                FailureStage(d["expected_failed_stage"])
                if d.get("expected_failed_stage")
                else None
            ),
            failure_reason=d.get("failure_reason"),
            notes=d.get("notes"),
        )


# --------------------------------------------------------------------------- #
# Dataset load / save helpers
# --------------------------------------------------------------------------- #

def load_dataset(path: str | Path) -> List[EvaluationCase]:
    """Load an evaluation dataset JSON file into a list of EvaluationCase."""
    path = Path(path)
    raw = json.loads(path.read_text())
    cases_raw = raw["cases"] if isinstance(raw, dict) and "cases" in raw else raw
    return [EvaluationCase.from_dict(c) for c in cases_raw]


def save_dataset(cases: List[EvaluationCase], path: str | Path, version: str = "v1") -> None:
    """Save a list of EvaluationCase back out as a versioned dataset JSON file."""
    path = Path(path)
    payload = {
        "version": version,
        "count": len(cases),
        "cases": [c.to_dict() for c in cases],
    }
    path.write_text(json.dumps(payload, indent=2))


def validate_dataset(cases: List[EvaluationCase]) -> None:
    """Basic integrity checks: unique ids, category/difficulty distribution."""
    ids = [c.id for c in cases]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise ValueError(f"Duplicate case ids found: {dupes}")