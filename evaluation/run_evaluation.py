"""
Run the analytics evaluation suite.

Usage:
    python -m evaluation.run_evaluation
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from database.connection import session_scope
from evaluation.analysis.failure_analyzer import analyze_failures
from evaluation.loaders.dataset_loader import load_evaluation_dataset
from evaluation.reports.evaluation_report import build_evaluation_report
from evaluation.runners.evaluation_runner import EvaluationRunner

from api.dependencies.analytics import build_analytics_service, get_nl_completion


PROJECT_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_DATASET_PATH = (
    PROJECT_ROOT
    / "evaluation"
    / "datasets"
    / "analytics_eval_v4.json"
)


def main() -> None:
    """Run the complete analytics evaluation pipeline."""

    print("=" * 70)
    print("ANALYTICS EVALUATION")
    print("=" * 70)

    print(f"\nLoading dataset: {DEFAULT_DATASET_PATH}")

    try:
        cases = load_evaluation_dataset(DEFAULT_DATASET_PATH)
    except Exception as exc:
        print(f"\nFailed to load evaluation dataset: {exc}")
        raise SystemExit(1) from exc

    print(f"Loaded {len(cases)} evaluation cases.")

    try:
        completion = get_nl_completion()

        with session_scope() as db_session:
            service = build_analytics_service(
                db_session=db_session,
                completion=completion,
            )

            runner = EvaluationRunner(service=service)

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

    failure_analysis = analyze_failures(results)

    print("\n" + "=" * 70)
    print("FAILURE ANALYSIS")
    print("=" * 70)

    if failure_analysis.failed_results == 0:
        print("\nNo failures to analyze — every case passed.")
    else:
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

    print("\n" + "=" * 70)
    print("EVALUATION COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()