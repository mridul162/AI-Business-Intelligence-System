"""
Unit tests for the failure analysis module.
"""

from __future__ import annotations

from types import SimpleNamespace

from evaluation.analysis.failure_analyzer import (
    FailureType,
    analyze_failures,
)


def _make_field_diff(
    *,
    field: str,
    expected: object,
    actual: object,
) -> SimpleNamespace:
    """Build a stand-in for a FieldDiff.

    `_classify_failure` only ever reads `.field` off these, so a plain
    attribute holder is sufficient here.
    """

    return SimpleNamespace(field=field, expected=expected, actual=actual)


def _make_result(
    *,
    case_id: str = "EVAL-001",
    question: str = "What is our net sales?",
    category: str = "direct_metric",
    difficulty: str = "easy",
    passed: bool,
    actual_status: str,
    actual_failed_stage: str | None = None,
    expected_failed_stage: str | None = None,
    field_diffs: list[SimpleNamespace] | None = None,
    error: str | None = None,
) -> SimpleNamespace:
    """Build a stand-in for an EvaluationResult.

    `_classify_failure` reads these fields directly off the result via
    attribute access, so a plain attribute holder is sufficient here.
    """

    return SimpleNamespace(
        case_id=case_id,
        question=question,
        category=category,
        difficulty=difficulty,
        passed=passed,
        actual_status=actual_status,
        actual_failed_stage=actual_failed_stage,
        expected_failed_stage=expected_failed_stage,
        field_diffs=field_diffs or [],
        error=error,
    )


def test_analyze_excludes_passed_results() -> None:
    result = _make_result(
        case_id="EVAL-001",
        passed=True,
        actual_status="success",
    )

    analysis = analyze_failures([result]) # type: ignore

    assert analysis.total_results == 1
    assert analysis.failed_results == 0
    assert analysis.failures == ()
    assert analysis.failure_counts == {}


def test_analyze_detects_metric_mismatch() -> None:
    result = _make_result(
        case_id="EVAL-001",
        passed=False,
        actual_status="success",
        field_diffs=[
            _make_field_diff(
                field="metrics",
                expected=["net_sales"],
                actual=["total_expenses"],
            ),
        ],
    )

    analysis = analyze_failures([result]) # type: ignore

    assert analysis.failed_results == 1

    failure = analysis.failures[0]

    assert failure.case_id == "EVAL-001"
    assert FailureType.METRIC_MISMATCH in failure.failure_types


def test_analyze_detects_missing_metric() -> None:
    result = _make_result(
        passed=False,
        actual_status="success",
        field_diffs=[
            _make_field_diff(
                field="metrics",
                expected=["net_sales"],
                actual=[],
            ),
        ],
    )

    analysis = analyze_failures([result]) # type: ignore

    failure = analysis.failures[0]

    assert FailureType.METRIC_MISMATCH in failure.failure_types


def test_analyze_detects_dimension_mismatch() -> None:
    result = _make_result(
        passed=False,
        actual_status="success",
        field_diffs=[
            _make_field_diff(
                field="dimensions",
                expected=["payment_method"],
                actual=["product_category"],
            ),
        ],
    )

    analysis = analyze_failures([result]) # type: ignore

    failure = analysis.failures[0]

    assert FailureType.DIMENSION_MISMATCH in failure.failure_types


def test_analyze_detects_filter_mismatch() -> None:
    expected_filter = {
        "dimension": "payment_method",
        "operator": "eq",
        "value": "cash",
    }

    actual_filter = {
        "dimension": "payment_method",
        "operator": "eq",
        "value": "credit",
    }

    result = _make_result(
        passed=False,
        actual_status="success",
        field_diffs=[
            _make_field_diff(
                field="filters",
                expected=[expected_filter],
                actual=[actual_filter],
            ),
        ],
    )

    analysis = analyze_failures([result]) # type: ignore

    failure = analysis.failures[0]

    assert FailureType.FILTER_MISMATCH in failure.failure_types


def test_analyze_detects_time_grain_mismatch() -> None:
    result = _make_result(
        passed=False,
        actual_status="success",
        field_diffs=[
            _make_field_diff(
                field="time_grain",
                expected="monthly",
                actual="daily",
            ),
        ],
    )

    analysis = analyze_failures([result]) # type: ignore

    failure = analysis.failures[0]

    assert FailureType.TIME_GRAIN_MISMATCH in failure.failure_types


def test_analyze_detects_pipeline_failure() -> None:
    result = _make_result(
        passed=False,
        actual_status="failure",
        actual_failed_stage="semantic_resolution",
        error="Semantic resolution failed.",
    )

    analysis = analyze_failures([result]) # type: ignore

    assert analysis.failed_results == 1

    failure = analysis.failures[0]

    assert FailureType.PIPELINE_FAILURE in failure.failure_types
    assert failure.error == "Semantic resolution failed."


def test_analyze_detects_unexpected_error() -> None:
    result = _make_result(
        passed=False,
        actual_status="failure",
        actual_failed_stage="unexpected_error",
        error="Unexpected database connection error.",
    )

    analysis = analyze_failures([result]) # type: ignore

    assert analysis.failed_results == 1

    failure = analysis.failures[0]

    assert FailureType.UNEXPECTED_ERROR in failure.failure_types
    assert failure.error == "Unexpected database connection error."


def test_analyze_detects_multiple_failure_categories() -> None:
    result = _make_result(
        passed=False,
        actual_status="success",
        field_diffs=[
            _make_field_diff(
                field="metrics",
                expected=["net_sales"],
                actual=["total_expenses"],
            ),
            _make_field_diff(
                field="dimensions",
                expected=["payment_method"],
                actual=[],
            ),
            _make_field_diff(
                field="time_grain",
                expected="monthly",
                actual="daily",
            ),
        ],
    )

    analysis = analyze_failures([result]) # type: ignore

    failure = analysis.failures[0]

    assert FailureType.METRIC_MISMATCH in failure.failure_types
    assert FailureType.DIMENSION_MISMATCH in failure.failure_types
    assert FailureType.TIME_GRAIN_MISMATCH in failure.failure_types


def test_analyze_counts_failures_by_category() -> None:
    results = [
        _make_result(
            case_id="EVAL-001",
            passed=False,
            actual_status="success",
            field_diffs=[
                _make_field_diff(
                    field="metrics",
                    expected=["net_sales"],
                    actual=["total_expenses"],
                ),
            ],
        ),
        _make_result(
            case_id="EVAL-002",
            passed=False,
            actual_status="success",
            field_diffs=[
                _make_field_diff(
                    field="metrics",
                    expected=["total_orders"],
                    actual=[],
                ),
            ],
        ),
        _make_result(
            case_id="EVAL-003",
            passed=False,
            actual_status="success",
            field_diffs=[
                _make_field_diff(
                    field="time_grain",
                    expected="monthly",
                    actual="daily",
                ),
            ],
        ),
    ]

    analysis = analyze_failures(results) # type: ignore

    assert analysis.failed_results == 3

    assert (
        analysis.failure_counts[FailureType.METRIC_MISMATCH.value] == 2
    )

    assert (
        analysis.failure_counts[FailureType.TIME_GRAIN_MISMATCH.value]
        == 1
    )


def test_analyze_returns_all_failed_case_ids() -> None:
    results = [
        _make_result(
            case_id="EVAL-001",
            passed=False,
            actual_status="success",
            field_diffs=[
                _make_field_diff(
                    field="metrics",
                    expected=["net_sales"],
                    actual=[],
                ),
            ],
        ),
        _make_result(
            case_id="EVAL-002",
            passed=False,
            actual_status="success",
            field_diffs=[
                _make_field_diff(
                    field="time_grain",
                    expected="monthly",
                    actual="daily",
                ),
            ],
        ),
        _make_result(
            case_id="EVAL-003",
            passed=True,
            actual_status="success",
        ),
    ]

    analysis = analyze_failures(results) # type: ignore

    case_ids = {failure.case_id for failure in analysis.failures}

    assert case_ids == {
        "EVAL-001",
        "EVAL-002",
    }


def test_analyze_handles_empty_results() -> None:
    analysis = analyze_failures([])

    assert analysis.total_results == 0
    assert analysis.failed_results == 0
    assert analysis.failures == ()
    assert analysis.failure_counts == {}