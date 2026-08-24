from dataclasses import dataclass
from enum import Enum

import pytest

from evaluation.reports.evaluation_report import (
    build_evaluation_report,
)


class ResultStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    PIPELINE_FAILURE = "pipeline_failure"
    UNEXPECTED_ERROR = "unexpected_error"


@dataclass(frozen=True)
class FakeCase:
    id: str
    category: str
    difficulty: str


@dataclass(frozen=True)
class FakeResult:
    case: FakeCase
    passed: bool
    status: ResultStatus


def make_result(
    *,
    case_id: str,
    category: str = "direct_metric",
    difficulty: str = "easy",
    passed: bool = True,
    status: ResultStatus | None = None,
) -> FakeResult:
    if status is None:
        status = (
            ResultStatus.PASSED
            if passed
            else ResultStatus.FAILED
        )

    return FakeResult(
        case=FakeCase(
            id=case_id,
            category=category,
            difficulty=difficulty,
        ),
        passed=passed,
        status=status,
    )


def test_build_evaluation_report_aggregates_overall_results() -> None:
    results = [
        make_result(case_id="eval_001", passed=True),
        make_result(case_id="eval_002", passed=True),
        make_result(case_id="eval_003", passed=False),
        make_result(case_id="eval_004", passed=False),
    ]

    report = build_evaluation_report(results)

    assert report.total_cases == 4
    assert report.passed_cases == 2
    assert report.failed_cases == 2
    assert report.accuracy == 50.0


def test_build_evaluation_report_groups_results_by_category() -> None:
    results = [
        make_result(
            case_id="eval_001",
            category="direct_metric",
            passed=True,
        ),
        make_result(
            case_id="eval_002",
            category="direct_metric",
            passed=False,
        ),
        make_result(
            case_id="eval_003",
            category="time_based",
            passed=True,
        ),
        make_result(
            case_id="eval_004",
            category="time_based",
            passed=True,
        ),
    ]

    report = build_evaluation_report(results)

    direct_metric = report.by_category["direct_metric"]
    assert direct_metric.total == 2
    assert direct_metric.passed == 1
    assert direct_metric.failed == 1
    assert direct_metric.accuracy == 50.0

    time_based = report.by_category["time_based"]
    assert time_based.total == 2
    assert time_based.passed == 2
    assert time_based.failed == 0
    assert time_based.accuracy == 100.0


def test_build_evaluation_report_groups_results_by_difficulty() -> None:
    results = [
        make_result(
            case_id="eval_001",
            difficulty="easy",
            passed=True,
        ),
        make_result(
            case_id="eval_002",
            difficulty="easy",
            passed=False,
        ),
        make_result(
            case_id="eval_003",
            difficulty="hard",
            passed=False,
        ),
    ]

    report = build_evaluation_report(results)

    easy = report.by_difficulty["easy"]
    assert easy.total == 2
    assert easy.passed == 1
    assert easy.failed == 1
    assert easy.accuracy == 50.0

    hard = report.by_difficulty["hard"]
    assert hard.total == 1
    assert hard.passed == 0
    assert hard.failed == 1
    assert hard.accuracy == 0.0


def test_build_evaluation_report_records_failed_case_ids() -> None:
    results = [
        make_result(case_id="eval_001", passed=True),
        make_result(case_id="eval_002", passed=False),
        make_result(case_id="eval_003", passed=False),
    ]

    report = build_evaluation_report(results)

    assert report.failed_case_ids == (
        "eval_002",
        "eval_003",
    )


def test_build_evaluation_report_counts_pipeline_failures() -> None:
    results = [
        make_result(
            case_id="eval_001",
            passed=False,
            status=ResultStatus.PIPELINE_FAILURE,
        ),
        make_result(
            case_id="eval_002",
            passed=False,
            status=ResultStatus.PIPELINE_FAILURE,
        ),
        make_result(
            case_id="eval_003",
            passed=False,
            status=ResultStatus.FAILED,
        ),
    ]

    report = build_evaluation_report(results)

    assert report.pipeline_failures == 2
    assert report.unexpected_errors == 0


def test_build_evaluation_report_counts_unexpected_errors() -> None:
    results = [
        make_result(
            case_id="eval_001",
            passed=False,
            status=ResultStatus.UNEXPECTED_ERROR,
        ),
        make_result(
            case_id="eval_002",
            passed=False,
            status=ResultStatus.FAILED,
        ),
    ]

    report = build_evaluation_report(results)

    assert report.pipeline_failures == 0
    assert report.unexpected_errors == 1


def test_build_evaluation_report_handles_empty_results() -> None:
    report = build_evaluation_report([])

    assert report.total_cases == 0
    assert report.passed_cases == 0
    assert report.failed_cases == 0
    assert report.accuracy == 0.0
    assert report.by_category == {}
    assert report.by_difficulty == {}
    assert report.pipeline_failures == 0
    assert report.unexpected_errors == 0
    assert report.failed_case_ids == ()


def test_build_evaluation_report_supports_dictionary_results() -> None:
    results = [
        {
            "case": {
                "id": "eval_001",
                "category": "direct_metric",
                "difficulty": "easy",
            },
            "passed": True,
            "status": "passed",
        },
        {
            "case": {
                "id": "eval_002",
                "category": "filter",
                "difficulty": "medium",
            },
            "passed": False,
            "status": "pipeline_failure",
        },
    ]

    report = build_evaluation_report(results)

    assert report.total_cases == 2
    assert report.passed_cases == 1
    assert report.failed_cases == 1
    assert report.accuracy == 50.0
    assert report.pipeline_failures == 1

    assert report.by_category["direct_metric"].passed == 1
    assert report.by_category["filter"].failed == 1

    assert report.by_difficulty["easy"].passed == 1
    assert report.by_difficulty["medium"].failed == 1


@pytest.mark.parametrize(
    ("passed", "status", "expected_accuracy"),
    [
        (True, ResultStatus.PASSED, 100.0),
        (False, ResultStatus.FAILED, 0.0),
    ],
)
def test_build_evaluation_report_calculates_single_case_accuracy(
    passed: bool,
    status: ResultStatus,
    expected_accuracy: float,
) -> None:
    report = build_evaluation_report(
        [
            make_result(
                case_id="eval_001",
                passed=passed,
                status=status,
            )
        ]
    )

    assert report.accuracy == expected_accuracy