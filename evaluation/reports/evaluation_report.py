"""
Evaluation report aggregation.

Transforms individual evaluation results produced by EvaluationRunner
into an aggregate report that can be used to understand overall system
performance and identify weak areas by category and difficulty.

This module does not execute evaluation cases. Its responsibility is
limited to aggregating already-produced evaluation results.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class EvaluationBreakdown:
    """Aggregate performance for one evaluation group."""

    total: int
    passed: int
    failed: int
    accuracy: float


@dataclass(frozen=True)
class EvaluationReport:
    """Aggregate report for a complete evaluation run."""

    total_cases: int
    passed_cases: int
    failed_cases: int
    accuracy: float

    by_category: dict[str, EvaluationBreakdown]
    by_difficulty: dict[str, EvaluationBreakdown]

    pipeline_failures: int
    unexpected_errors: int

    failed_case_ids: tuple[str, ...]


def _get_value(
    result: Any,
    field: str,
    default: Any = None,
) -> Any:
    """Read a field from either an object or a dictionary."""

    if isinstance(result, dict):
        return result.get(field, default)

    return getattr(result, field, default)


def _get_case(result: Any) -> Any:
    """Extract the evaluation case associated with a result."""

    return _get_value(result, "case")


def _get_case_value(
    result: Any,
    field: str,
    default: Any = None,
) -> Any:
    """Read a field from the evaluation case."""

    case = _get_case(result)

    if case is None:
        return default

    return _get_value(case, field, default)


def _get_result_status(result: Any) -> str | None:
    """Return the normalized result status."""

    status = _get_value(result, "status")

    if status is None:
        return None

    if hasattr(status, "value"):
        return str(status.value)

    return str(status)


def _result_passed(result: Any) -> bool:
    """Determine whether an evaluation result passed.

    The runner is expected to expose either a boolean `passed` field
    or a status value where `success` / `passed` represents success.
    """

    passed = _get_value(result, "passed")

    if passed is not None:
        return bool(passed)

    status = _get_result_status(result)

    if status is None:
        return False

    return status.lower() in {"passed", "success"}


def _result_case_id(result: Any) -> str:
    """Return the ID of the evaluated case."""

    case_id = _get_case_value(result, "id")

    if case_id is None:
        case_id = _get_value(result, "case_id", "unknown")

    return str(case_id)


def _result_category(result: Any) -> str:
    """Return the category of the evaluated case."""

    category = _get_case_value(result, "category")

    if category is None:
        category = _get_value(result, "category", "unknown")

    if hasattr(category, "value"):
        return str(category.value)

    return str(category)


def _result_difficulty(result: Any) -> str:
    """Return the difficulty of the evaluated case."""

    difficulty = _get_case_value(result, "difficulty")

    if difficulty is None:
        difficulty = _get_value(result, "difficulty", "unknown")

    if hasattr(difficulty, "value"):
        return str(difficulty.value)

    return str(difficulty)


def _build_breakdown(
    counts: dict[str, dict[str, int]],
) -> dict[str, EvaluationBreakdown]:
    """Convert mutable counters into immutable report objects."""

    breakdown: dict[str, EvaluationBreakdown] = {}

    for name, values in sorted(counts.items()):
        total = values["total"]
        passed = values["passed"]
        failed = values["failed"]

        accuracy = (passed / total * 100) if total else 0.0

        breakdown[name] = EvaluationBreakdown(
            total=total,
            passed=passed,
            failed=failed,
            accuracy=round(accuracy, 2),
        )

    return breakdown


def build_evaluation_report(
    results: Iterable[Any],
) -> EvaluationReport:
    """Build an aggregate report from evaluation results.

    Args:
        results:
            Individual results returned by EvaluationRunner.

    Returns:
        An EvaluationReport containing overall performance, category
        breakdowns, difficulty breakdowns, failure counts, and failed
        case IDs.
    """

    results = list(results)

    total_cases = len(results)
    passed_cases = 0
    failed_case_ids: list[str] = []

    pipeline_failures = 0
    unexpected_errors = 0

    category_counts: dict[str, dict[str, int]] = defaultdict(
        lambda: {"total": 0, "passed": 0, "failed": 0}
    )

    difficulty_counts: dict[str, dict[str, int]] = defaultdict(
        lambda: {"total": 0, "passed": 0, "failed": 0}
    )

    for result in results:
        passed = _result_passed(result)
        category = _result_category(result)
        difficulty = _result_difficulty(result)

        category_counts[category]["total"] += 1
        difficulty_counts[difficulty]["total"] += 1

        if passed:
            passed_cases += 1
            category_counts[category]["passed"] += 1
            difficulty_counts[difficulty]["passed"] += 1
        else:
            failed_case_ids.append(_result_case_id(result))
            category_counts[category]["failed"] += 1
            difficulty_counts[difficulty]["failed"] += 1

        status = _get_result_status(result)

        if status == "pipeline_failure":
            pipeline_failures += 1
        elif status == "unexpected_error":
            unexpected_errors += 1

    failed_cases = total_cases - passed_cases

    accuracy = (
        passed_cases / total_cases * 100
        if total_cases
        else 0.0
    )

    return EvaluationReport(
        total_cases=total_cases,
        passed_cases=passed_cases,
        failed_cases=failed_cases,
        accuracy=round(accuracy, 2),
        by_category=_build_breakdown(category_counts),
        by_difficulty=_build_breakdown(difficulty_counts),
        pipeline_failures=pipeline_failures,
        unexpected_errors=unexpected_errors,
        failed_case_ids=tuple(failed_case_ids),
    )