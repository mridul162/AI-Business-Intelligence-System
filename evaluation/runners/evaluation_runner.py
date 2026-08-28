"""
Evaluation runner for the AI Business Intelligence System.

Runs evaluation cases against the real analytical query pipeline and
produces structured evaluation results.
"""

from __future__ import annotations

import time
from typing import Any, Iterable

from etl.analytics.service.analytical_query_service import (
    AnalyticalQueryService,
)

from evaluation.schemas.evaluation_case import EvaluationCase
from evaluation.schemas.evaluation_result import EvaluationResult, FieldDiff


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

            return self._build_unexpected_error_result(
                case=case,
                error=str(exc),
                latency_ms=latency_ms,
            )

        latency_ms = self._elapsed_ms(start_time)

        if not response.success:
            return self._evaluate_pipeline_failure(
                case=case,
                response=response,
                latency_ms=latency_ms,
            )

        return self._evaluate_success(
            case=case,
            response=response,
            latency_ms=latency_ms,
        )

    def run_cases(
        self,
        cases: Iterable[EvaluationCase],
    ) -> list[EvaluationResult]:
        """Run multiple evaluation cases."""

        return [self.run_case(case) for case in cases]

    def _evaluate_success(
        self,
        *,
        case: EvaluationCase,
        response: Any,
        latency_ms: float,
    ) -> EvaluationResult:
        """Evaluate a successful pipeline response."""

        if case.expected_status.value != "success":
            return EvaluationResult(
                case_id=case.id,
                question=case.question,
                category=case.category.value,
                difficulty=case.difficulty.value,
                expected_status=case.expected_status.value,
                actual_status="success",
                passed=False,
                actual_failed_stage=None,
                expected_failed_stage=self._expected_failed_stage(case),
                field_diffs=[],
                error=None,
                reason=(
                    "pipeline succeeded but the evaluation case "
                    "expected the pipeline to fail"
                ),
                latency_ms=latency_ms,
            )

        if case.expected is None:
            return EvaluationResult(
                case_id=case.id,
                question=case.question,
                category=case.category.value,
                difficulty=case.difficulty.value,
                expected_status=case.expected_status.value,
                actual_status="success",
                passed=False,
                actual_failed_stage=None,
                expected_failed_stage=self._expected_failed_stage(case),
                field_diffs=[],
                error=None,
                reason=(
                    "evaluation case expects success but has no "
                    "expected analytical output"
                ),
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
            expected_failed_stage=self._expected_failed_stage(case),
            field_diffs=field_diffs,
            error=None,
            reason=(
                None
                if passed
                else "actual output did not match expected"
            ),
            latency_ms=latency_ms,
        )

    def _evaluate_pipeline_failure(
        self,
        *,
        case: EvaluationCase,
        response: Any,
        latency_ms: float,
    ) -> EvaluationResult:
        """Evaluate a pipeline response that failed."""

        actual_failed_stage = response.error_stage
        expected_failed_stage = self._expected_failed_stage(case)

        passed = (
            case.expected_status.value == "failure"
            and actual_failed_stage == expected_failed_stage
        )

        if case.expected_status.value == "success":
            reason = "pipeline failed but the evaluation case expected success"

        elif expected_failed_stage is None:
            reason = (
                "evaluation case expected failure but does not define "
                "an expected failure stage"
            )

        elif actual_failed_stage != expected_failed_stage:
            reason = (
                "pipeline failed at a different stage than expected"
            )

        else:
            reason = None

        return EvaluationResult(
            case_id=case.id,
            question=case.question,
            category=case.category.value,
            difficulty=case.difficulty.value,
            expected_status=case.expected_status.value,
            actual_status="failure",
            passed=passed,
            actual_failed_stage=actual_failed_stage,
            expected_failed_stage=expected_failed_stage,
            field_diffs=[],
            error=response.error,
            reason=reason,
            latency_ms=latency_ms,
        )

    def _build_unexpected_error_result(
        self,
        *,
        case: EvaluationCase,
        error: str,
        latency_ms: float,
    ) -> EvaluationResult:
        """Build a result for an exception escaping the pipeline."""

        expected_failed_stage = self._expected_failed_stage(case)

        passed = (
            case.expected_status.value == "failure"
            and expected_failed_stage == "unexpected_error"
        )

        return EvaluationResult(
            case_id=case.id,
            question=case.question,
            category=case.category.value,
            difficulty=case.difficulty.value,
            expected_status=case.expected_status.value,
            actual_status="failure",
            passed=passed,
            actual_failed_stage="unexpected_error",
            expected_failed_stage=expected_failed_stage,
            field_diffs=[],
            error=error,
            reason=(
                None
                if passed
                else "unexpected exception escaped the analytical pipeline"
            ),
            latency_ms=latency_ms,
        )

    @staticmethod
    def _elapsed_ms(start_time: float) -> float:
        """Return elapsed time in milliseconds."""

        return round((time.perf_counter() - start_time) * 1000, 2)

    @staticmethod
    def _expected_failed_stage(case: EvaluationCase) -> str | None:
        """Return the expected failure stage as a normalized string."""

        if case.expected_failed_stage is None:
            return None

        return case.expected_failed_stage.value

    @staticmethod
    def _expected(case: EvaluationCase) -> dict[str, Any]:
        """Extract and normalize expected successful analytical output."""

        expected = case.expected

        if expected is None:
            raise ValueError(
                f"Evaluation case '{case.id}' does not define expected "
                "output for a successful evaluation."
            )

        return {
            "metrics": list(expected.metrics),
            "dimensions": list(expected.dimensions),
            "filters": [
                {
                    "dimension": filt.field,
                    "operator": _SYMBOL_TO_OPERATOR_NAME.get(
                        filt.operator,
                        filt.operator,
                    ),
                    "value": filt.value,
                }
                for filt in expected.filters
            ],
            "time_grain": expected.time_grain,
        }

    @staticmethod
    def _extract_actual(response: Any) -> dict[str, Any]:
        """Extract the resolved query representation from a response."""

        query = response.query

        if query is None:
            raise ValueError(
                "Analytical service returned success=True but query=None."
            )

        return {
            "metrics": list(query.metrics),
            "dimensions": list(query.dimensions),
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
        """Return one FieldDiff per mismatched top-level field."""

        diffs: list[FieldDiff] = []

        for key in (
            "metrics",
            "dimensions",
            "filters",
            "time_grain",
        ):
            if expected[key] != actual[key]:
                diffs.append(
                    FieldDiff(
                        field=key,
                        expected=expected[key],
                        actual=actual[key],
                    )
                )

        return diffs