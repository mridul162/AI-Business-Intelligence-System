"""
Evaluation failure analysis.

Analyzes failed evaluation results and identifies which parts of the
expected analytical query did not match the actual system output.

The analyzer does not run the analytical system and does not calculate
evaluation pass/fail status. Those responsibilities belong to
EvaluationRunner.

Its responsibility is:

    EvaluationResult objects
            |
            v
    Failed results
            |
            v
    Classify each result's field_diffs / failure stage
            |
            v
    Aggregate failure patterns

This provides the diagnostic layer needed to understand why evaluation
cases fail before changing prompts, aliases, semantic resolution logic,
or analytical capabilities.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from evaluation.schemas.evaluation_result import EvaluationResult, FieldDiff


class FailureType(str, Enum):
    """Categories of analytical evaluation failures."""

    METRIC_MISMATCH = "metric_mismatch"
    DIMENSION_MISMATCH = "dimension_mismatch"
    FILTER_MISMATCH = "filter_mismatch"
    TIME_GRAIN_MISMATCH = "time_grain_mismatch"
    PIPELINE_FAILURE = "pipeline_failure"
    UNEXPECTED_ERROR = "unexpected_error"
    UNKNOWN_MISMATCH = "unknown_mismatch"


# Maps EvaluationResult.field_diffs[i].field (see EvaluationRunner._diff,
# which only ever emits "metrics", "dimensions", "filters", "time_grain")
# to the corresponding failure category.
_FIELD_TO_FAILURE_TYPE: dict[str, FailureType] = {
    "metrics": FailureType.METRIC_MISMATCH,
    "dimensions": FailureType.DIMENSION_MISMATCH,
    "filters": FailureType.FILTER_MISMATCH,
    "time_grain": FailureType.TIME_GRAIN_MISMATCH,
}


@dataclass(frozen=True)
class FailureDetail:
    """Detailed diagnosis for one failed evaluation case."""

    case_id: str
    question: str
    category: str
    difficulty: str
    failure_types: tuple[FailureType, ...]
    field_diffs: tuple[FieldDiff, ...]
    actual_failed_stage: str | None
    expected_failed_stage: str | None
    error: str | None


@dataclass(frozen=True)
class FailureAnalysis:
    """Aggregated analysis of evaluation failures."""

    total_results: int
    failed_results: int
    failure_counts: dict[str, int]
    failures: tuple[FailureDetail, ...]


def _classify_failure(result: EvaluationResult) -> FailureDetail:
    """Classify one failed evaluation result."""

    failure_types: list[FailureType] = []

    if result.actual_status == "failure":
        if result.actual_failed_stage == "unexpected_error":
            failure_types.append(FailureType.UNEXPECTED_ERROR)
        else:
            failure_types.append(FailureType.PIPELINE_FAILURE)
    else:
        for diff in result.field_diffs:
            failure_types.append(
                _FIELD_TO_FAILURE_TYPE.get(
                    diff.field,
                    FailureType.UNKNOWN_MISMATCH,
                )
            )

    if not failure_types:
        failure_types.append(FailureType.UNKNOWN_MISMATCH)

    return FailureDetail(
        case_id=result.case_id,
        question=result.question,
        category=result.category,
        difficulty=result.difficulty,
        failure_types=tuple(failure_types),
        field_diffs=tuple(result.field_diffs),
        actual_failed_stage=result.actual_failed_stage,
        expected_failed_stage=result.expected_failed_stage,
        error=result.error,
    )


def analyze_failures(
    results: Iterable[EvaluationResult],
) -> FailureAnalysis:
    """Analyze all failed evaluation results.

    Args:
        results:
            Evaluation results produced by EvaluationRunner.

    Returns:
        FailureAnalysis containing per-case diagnostics and aggregated
        failure counts.
    """

    results_list = list(results)

    failures: list[FailureDetail] = []
    counts: Counter[str] = Counter()

    for result in results_list:
        if result.passed:
            continue

        detail = _classify_failure(result)
        failures.append(detail)

        for failure_type in detail.failure_types:
            counts[failure_type.value] += 1

    return FailureAnalysis(
        total_results=len(results_list),
        failed_results=len(failures),
        failure_counts=dict(counts),
        failures=tuple(failures),
    )