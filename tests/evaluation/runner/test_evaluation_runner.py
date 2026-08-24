from __future__ import annotations

from dataclasses import dataclass

import pytest

from etl.analytics.query.models import (
    FilterOperator,
    QueryFilter,
    QueryRequest,
)
from evaluation.runners.evaluation_runner import EvaluationRunner
from evaluation.schemas.evaluation_case import (
    Difficulty,
    EvalCategory,
    EvaluationCase,
    ExpectedFilter,
    ExpectedOutput,
    ExpectedStatus,
)


# -------------------------------------------------------------------
# Test doubles
# -------------------------------------------------------------------


@dataclass
class FakeResponse:
    success: bool
    query: QueryRequest | None = None
    error_stage: str | None = None
    error: str | None = None


class FakeAnalyticalQueryService:
    def __init__(
        self,
        response: FakeResponse | None = None,
        exception: Exception | None = None,
    ) -> None:
        self.response = response
        self.exception = exception
        self.questions: list[str] = []

    def query(self, text: str):
        self.questions.append(text)

        if self.exception is not None:
            raise self.exception

        return self.response


# -------------------------------------------------------------------
# Fixtures
# -------------------------------------------------------------------


@pytest.fixture
def evaluation_case() -> EvaluationCase:
    return EvaluationCase(
        id="eval_001",
        question="What were the net sales last month?",
        category=EvalCategory.DIRECT_METRIC,
        difficulty=Difficulty.EASY,
        expected_status=ExpectedStatus.SUCCESS,
        expected=ExpectedOutput(
            metrics=["net_sales"],
            dimensions=[],
            filters=[],
            time_grain=None,
            time_range=None,
        ),
    )


# -------------------------------------------------------------------
# run_case: successful evaluation
# -------------------------------------------------------------------


def test_run_case_passes_when_actual_matches_expected(
    evaluation_case: EvaluationCase,
) -> None:
    query = QueryRequest(
        metrics=("net_sales",),
        dimensions=(),
        filters=(),
        time_grain=None,
    )

    service = FakeAnalyticalQueryService(
        response=FakeResponse(
            success=True,
            query=query,
        )
    )

    runner = EvaluationRunner(service) # type: ignore

    result = runner.run_case(evaluation_case)

    assert result.case_id == "eval_001"
    assert result.question == evaluation_case.question
    assert result.category == "direct_metric"
    assert result.difficulty == "easy"
    assert result.expected_status == "success"
    assert result.actual_status == "success"
    assert result.passed is True
    assert result.actual_failed_stage is None
    assert result.field_diffs == []
    assert result.error is None
    assert result.latency_ms >= 0 # type: ignore

    assert service.questions == [
        "What were the net sales last month?"
    ]


# -------------------------------------------------------------------
# run_case: evaluation mismatch
# -------------------------------------------------------------------


def test_run_case_fails_when_actual_does_not_match_expected(
    evaluation_case: EvaluationCase,
) -> None:
    query = QueryRequest(
        metrics=("total_expenses",),
        dimensions=(),
        filters=(),
        time_grain=None,
    )

    service = FakeAnalyticalQueryService(
        response=FakeResponse(
            success=True,
            query=query,
        )
    )

    runner = EvaluationRunner(service) # type: ignore

    result = runner.run_case(evaluation_case)

    # Pipeline ran fine, but produced the wrong answer -- distinct from a
    # hard pipeline failure, per EvaluationResult's docstring.
    assert result.passed is False
    assert result.actual_status == "success"
    assert result.actual_failed_stage is None
    assert result.error is None

    metrics_diff = next(
        fd for fd in result.field_diffs if fd.field == "metrics"
    )
    assert metrics_diff.expected == ["net_sales"]
    assert metrics_diff.actual == ["total_expenses"]


# -------------------------------------------------------------------
# run_case: pipeline failure
# -------------------------------------------------------------------


def test_run_case_records_pipeline_failure(
    evaluation_case: EvaluationCase,
) -> None:
    service = FakeAnalyticalQueryService(
        response=FakeResponse(
            success=False,
            error_stage="semantic_resolution",
            error="Could not resolve metric 'sales'.",
        )
    )

    runner = EvaluationRunner(service) # type: ignore

    result = runner.run_case(evaluation_case)

    assert result.passed is False
    assert result.actual_status == "failure"
    assert result.field_diffs == []
    assert result.actual_failed_stage == "semantic_resolution"
    assert result.error == "Could not resolve metric 'sales'."
    assert result.latency_ms >= 0 # type: ignore


# -------------------------------------------------------------------
# run_case: unexpected exception
# -------------------------------------------------------------------


def test_run_case_records_unexpected_exception(
    evaluation_case: EvaluationCase,
) -> None:
    service = FakeAnalyticalQueryService(
        exception=RuntimeError("Database connection lost.")
    )

    runner = EvaluationRunner(service) # type: ignore

    result = runner.run_case(evaluation_case)

    assert result.passed is False
    assert result.actual_status == "failure"
    assert result.field_diffs == []
    # The runner tags unhandled exceptions with a synthetic stage name
    # rather than mapping them onto a real FailureStage member.
    assert result.actual_failed_stage == "unexpected_error"
    assert result.error == "Database connection lost."
    assert result.latency_ms >= 0 # type: ignore


# -------------------------------------------------------------------
# Filter normalization
# -------------------------------------------------------------------


def test_run_case_normalizes_filter_operator(
) -> None:
    case = EvaluationCase(
        id="eval_002",
        question="Show net sales for cash payments.",
        category=EvalCategory.FILTER,
        difficulty=Difficulty.EASY,
        expected_status=ExpectedStatus.SUCCESS,
        expected=ExpectedOutput(
            metrics=["net_sales"],
            dimensions=[],
            filters=[
                ExpectedFilter(
                    field="payment_method",
                    operator="=",
                    value="cash",
                ),
            ],
            time_grain=None,
            time_range=None,
        ),
    )

    query = QueryRequest(
        metrics=("net_sales",),
        dimensions=(),
        filters=(
            QueryFilter(
                dimension="payment_method",
                operator=FilterOperator.EQ,
                value="cash",
            ),
        ),
        time_grain=None,
    )

    service = FakeAnalyticalQueryService(
        response=FakeResponse(success=True, query=query)
    )

    runner = EvaluationRunner(service) # type: ignore

    result = runner.run_case(case)

    # FilterOperator.EQ on the actual side and "=" on the expected side
    # should be normalized to the same canonical form by the runner, so
    # no field diff should be recorded for "filters".
    assert result.passed is True
    assert not any(fd.field == "filters" for fd in result.field_diffs)


# -------------------------------------------------------------------
# Multiple cases
# -------------------------------------------------------------------


def test_run_cases_returns_result_for_every_case(
    evaluation_case: EvaluationCase,
) -> None:
    matching_query = QueryRequest(
        metrics=("net_sales",),
        dimensions=(),
        filters=(),
        time_grain=None,
    )

    service = FakeAnalyticalQueryService(
        response=FakeResponse(
            success=True,
            query=matching_query,
        )
    )

    runner = EvaluationRunner(service) # type: ignore

    second_case = EvaluationCase(
        id="eval_002",
        question="What is net sales?",
        category=EvalCategory.DIRECT_METRIC,
        difficulty=Difficulty.EASY,
        expected_status=ExpectedStatus.SUCCESS,
        expected=ExpectedOutput(
            metrics=["net_sales"],
            dimensions=[],
            filters=[],
            time_grain=None,
            time_range=None,
        ),
    )

    results = runner.run_cases(
        [evaluation_case, second_case]
    )

    assert len(results) == 2
    assert results[0].case_id == "eval_001"
    assert results[1].case_id == "eval_002"
    assert all(result.passed for result in results)

    assert service.questions == [
        evaluation_case.question,
        second_case.question,
    ]