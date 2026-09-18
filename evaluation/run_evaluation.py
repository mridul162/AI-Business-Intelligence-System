"""
Run the analytics evaluation suite.

Usage:
    python -m evaluation.run_evaluation
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from evaluation.analysis.failure_analyzer import (
    FailureAnalysis,
    analyze_failures,
)
from evaluation.loaders.dataset_loader import load_evaluation_dataset
from evaluation.reports.evaluation_report import (
    EvaluationReport,
    build_evaluation_report,
)
from evaluation.runners.evaluation_runner import EvaluationRunner
from evaluation.schemas.evaluation_case import EvaluationCase

from etl.analytics.application.analytics_application import AnalyticsApplication
from etl.analytics.application.factory import (
    create_analytics_application,
    get_nl_completion,
)
from etl.analytics.config import get_settings


PROJECT_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_DATASET_PATH = (
    PROJECT_ROOT
    / "evaluation"
    / "datasets"
    / "analytics_eval_v1.json"
)


def load_cases(dataset_path: Path) -> list[EvaluationCase]:
    """Load and validate evaluation cases from ``dataset_path``."""

    return load_evaluation_dataset(dataset_path)


def build_application() -> AnalyticsApplication:
    """Build the production analytics application for evaluation."""

    settings = get_settings()
    completion = get_nl_completion(settings)
    return create_analytics_application(
        settings=settings,
        completion=completion,
    )


def run_evaluation(
    *,
    dataset_path: Path = DEFAULT_DATASET_PATH,
    application: Any | None = None,
) -> tuple[EvaluationReport, FailureAnalysis]:
    """Run evaluation cases and return the structured report and analysis."""

    cases = load_cases(dataset_path)
    runner = EvaluationRunner(
        application=(
            application
            if application is not None
            else build_application()
        ),
    )
    results = runner.run_cases(cases)
    return build_evaluation_report(results), analyze_failures(results)


def _print_failure_analysis(failure_analysis) -> None:
    """Print the detailed failure analysis section."""

    print("\n" + "=" * 70)
    print("FAILURE ANALYSIS")
    print("=" * 70)

    if failure_analysis.failed_results == 0:
        print("\nNo failures to analyze — every case passed.")
        return

    print(
        json.dumps(
            {
                "total_results": failure_analysis.total_results,
                "failed_results": failure_analysis.failed_results,
                "failure_counts": failure_analysis.failure_counts,
                "failures": [
                    asdict(detail)
                    for detail in failure_analysis.failures
                ],
            },
            indent=2,
            default=str,
        )
    )


def main() -> None:
    """Run the complete analytics evaluation pipeline."""

    print("=" * 70)
    print("ANALYTICS EVALUATION")
    print("=" * 70)

    print(f"\nLoading dataset: {DEFAULT_DATASET_PATH}")

    try:
        cases = load_cases(DEFAULT_DATASET_PATH)
    except Exception as exc:
        print(f"\nFailed to load evaluation dataset: {exc}")
        raise SystemExit(1) from exc

    print(f"Loaded {len(cases)} evaluation cases.")

    try:
        application = build_application()
        runner = EvaluationRunner(application=application)
        print("\nRunning evaluation cases...\n")
        results = runner.run_cases(cases)

    except Exception:
        import traceback

        print("\nEvaluation execution failed:\n")
        traceback.print_exc()
        raise SystemExit(1)

    report = build_evaluation_report(results)

    print("=" * 70)
    print("EVALUATION REPORT")
    print("=" * 70)

    print(
        json.dumps(
            report,
            indent=2,
            default=str,
        )
    )

    _print_failure_analysis(analyze_failures(results))

    print("\n" + "=" * 70)
    print("EVALUATION COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()