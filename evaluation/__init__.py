"""
evaluation/

Phase 10 evaluation harness for the AI Business Intelligence System.

Subpackages:
    schemas/    Structured evaluation case schema (evaluation_case.py)
    datasets/   Versioned evaluation datasets (analytics_eval_v1.json, ...)
    runners/    Pipeline runners that execute cases against the live system
    metrics/    Scoring/aggregation logic (accuracy, failure taxonomy, etc.)
    reports/    Generated evaluation run reports

This __init__ intentionally does not import runners/metrics eagerly, since
Phase 10.1 only requires the dataset + schema to exist.
"""

from evaluation.schemas.evaluation_case import (  # noqa: F401
    Difficulty,
    EvalCategory,
    EvaluationCase,
    ExpectedFilter,
    ExpectedOutput,
    ExpectedStatus,
    FailureStage,
    load_dataset,
    save_dataset,
    validate_dataset,
)