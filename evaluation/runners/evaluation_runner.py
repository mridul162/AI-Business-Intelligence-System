"""
Evaluation runner for the AI Business Intelligence System.

Runs evaluation cases against the real analytical query pipeline and
produces structured evaluation results.

The runner is intentionally independent of the API layer. It evaluates
the AnalyticalQueryService directly:

    EvaluationCase
          |
          v
    AnalyticalQueryService.query(question)
          |
          v
    AnalyticalQueryResponse
          |
          v
    Expected vs Actual Comparison
          |
          v
    EvaluationResult

This allows offline, repeatable evaluation without starting FastAPI or
sending HTTP requests.

The runner focuses on pipeline correctness rather than HTTP behavior.
It can identify whether a case passed and, when it failed, capture the
pipeline stage and error returned by the analytical service.
"""

from __future__ import annotations

import time
from typing import Any, Iterable

from etl.analytics.service.analytical_query_service import (
    AnalyticalQueryService,
)

from evaluation.schemas.evaluation_case import EvaluationCase
from evaluation.schemas.evaluation_result import EvaluationResult, FieldDiff

# ExpectedFilter.operator uses symbolic form ("=", "!=", ">", ">=", "<", "<=").
# QueryFilter.operator (the actual/pipeline side) is a FilterOperator enum
# whose .value is the short name ("eq", "ne", "gt", "gte", "lt", "lte").
# NOTE: this mapping assumes those are FilterOperator's actual enum values —
# confirm against etl.analytics.query.models.FilterOperator and adjust if not.
_SYMBOL_TO_OPERATOR_NAME = {
    "=": "eq",
    "!=": "ne",
    ">": "gt",
    ">=": "gte",
    "<": "lt",
    "<=": "lte",
}


class EvaluationRunner:
    """Run analytical evaluation cases against an AnalyticalQueryService."""

    def __init__(self, service: AnalyticalQueryService) -> None:
        self.service = service

    def run_case(self, case: EvaluationCase) -> EvaluationResult:
        """Run one evaluation case and return its structured result."""

        start_time = time.perf_counter()

        try:
            response = self.service.query(case.question)

        except Exception as exc:
            latency_ms = self._elapsed_ms(start_time)

            return EvaluationResult(
                case_id=case.id,
                question=case.question,
                category=case.category.value,
                difficulty=case.difficulty.value,
                expected_status=case.expected_status.value,
                actual_status="failure",
                passed=False,
                actual_failed_stage="unexpected_error",
                expected_failed_stage=(
                    case.expected_failed_stage.value
                    if case.expected_failed_stage is not None
                    else None
                ),
                error=str(exc),
                latency_ms=latency_ms,
            )

        latency_ms = self._elapsed_ms(start_time)

        if not response.success:
            return EvaluationResult(
                case_id=case.id,
                question=case.question,
                category=case.category.value,
                difficulty=case.difficulty.value,
                expected_status=case.expected_status.value,
                actual_status="failure",
                passed=False,
                actual_failed_stage=response.error_stage,
                expected_failed_stage=(
                    case.expected_failed_stage.value
                    if case.expected_failed_stage is not None
                    else None
                ),
                error=response.error,
                latency_ms=latency_ms,
            )

        actual = self._extract_actual(response)
        expected = self._expected(case)

        field_diffs = self._diff(expected, actual)
        passed = not field_diffs

        return EvaluationResult(
            case_id=case.id,
            question=case.question,
            category=case.category.value,
            difficulty=case.difficulty.value,
            expected_status=case.expected_status.value,
            actual_status="success",
            passed=passed,
            actual_failed_stage=None,
            expected_failed_stage=(
                case.expected_failed_stage.value
                if case.expected_failed_stage is not None
                else None
            ),
            field_diffs=field_diffs,
            error=None,
            reason=None if passed else "actual output did not match expected",
            latency_ms=latency_ms,
        )

    def run_cases(
        self,
        cases: Iterable[EvaluationCase],
    ) -> list[EvaluationResult]:
        """Run multiple evaluation cases."""

        return [self.run_case(case) for case in cases]

    @staticmethod
    def _elapsed_ms(start_time: float) -> float:
        """Return elapsed time in milliseconds."""

        return round((time.perf_counter() - start_time) * 1000, 2)

    @staticmethod
    def _expected(case: EvaluationCase) -> dict[str, Any]:
        """Extract the expected analytical representation from a case.

        Keep this method aligned with EvaluationCase.expected
        (an ExpectedOutput). The runner does not interpret expectations
        itself; it simply normalizes them into a dictionary that can be
        compared with the actual system output.
        """

        expected = case.expected

        return {
            "metrics": list(getattr(expected, "metrics")),
            "dimensions": list(getattr(expected, "dimensions")),
            "filters": [
                {
                    "dimension": filt.field,
                    "operator": _SYMBOL_TO_OPERATOR_NAME.get(
                        filt.operator, filt.operator
                    ),
                    "value": filt.value,
                }
                for filt in getattr(expected, "filters")
            ],
            "time_grain": getattr(expected, "time_grain"),
        }

    @staticmethod
    def _extract_actual(response: Any) -> dict[str, Any]:
        """Extract the resolved query representation from a response."""

        query = response.query

        return {
            "metrics": list(getattr(query, "metrics")),
            "dimensions": list(getattr(query, "dimensions")),
            "filters": [
                {
                    "dimension": filt.dimension,
                    "operator": (
                        filt.operator.value
                        if hasattr(filt.operator, "value")
                        else filt.operator
                    ),
                    "value": filt.value,
                }
                for filt in query.filters
            ],
            "time_grain": (
                query.time_grain.value
                if query.time_grain is not None
                and hasattr(query.time_grain, "value")
                else query.time_grain
            ),
        }

    @staticmethod
    def _diff(
        expected: dict[str, Any],
        actual: dict[str, Any],
    ) -> list[FieldDiff]:
        """Return one FieldDiff per mismatched top-level field.

        Metrics and dimensions are compared as ordered lists because the
        evaluation dataset should define the intended query structure
        explicitly. Filters are normalized before comparison to avoid
        differences caused by Enum representations.
        """

        diffs: list[FieldDiff] = []

        for key in ("metrics", "dimensions", "filters", "time_grain"):
            if expected[key] != actual[key]:
                diffs.append(
                    FieldDiff(
                        field=key,
                        expected=expected[key],
                        actual=actual[key],
                    )
                )

        return diffs