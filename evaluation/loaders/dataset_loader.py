"""
Evaluation dataset loader.

Loads evaluation cases from a JSON dataset and validates every record
through the EvaluationCase schema.

The loader is responsible only for:

    JSON file
        |
        v
    Python data
        |
        v
    EvaluationCase validation
        |
        v
    list[EvaluationCase]

It does not run the analytical system, calculate metrics, or evaluate
results. Those responsibilities belong to EvaluationRunner and the
reporting layer.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from evaluation.schemas.evaluation_case import EvaluationCase


class DatasetLoadError(Exception):
    """Raised when an evaluation dataset cannot be loaded or validated."""


def load_evaluation_dataset(path: str | Path) -> list[EvaluationCase]:
    """Load and validate evaluation cases from a JSON dataset.

    Args:
        path: Path to the JSON evaluation dataset.

    Returns:
        A list of validated EvaluationCase objects.

    Raises:
        DatasetLoadError:
            If the file does not exist, cannot be read, contains invalid
            JSON, has an unsupported top-level structure, or contains
            invalid evaluation cases.
    """

    dataset_path = Path(path)

    if not dataset_path.exists():
        raise DatasetLoadError(
            f"Evaluation dataset does not exist: {dataset_path}"
        )

    if not dataset_path.is_file():
        raise DatasetLoadError(
            f"Evaluation dataset path is not a file: {dataset_path}"
        )

    try:
        with dataset_path.open(
            "r",
            encoding="utf-8",
        ) as file:
            data: Any = json.load(file)

    except json.JSONDecodeError as exc:
        raise DatasetLoadError(
            f"Invalid JSON in evaluation dataset "
            f"'{dataset_path}': {exc.msg}"
        ) from exc

    except OSError as exc:
        raise DatasetLoadError(
            f"Could not read evaluation dataset "
            f"'{dataset_path}': {exc}"
        ) from exc

    if isinstance(data, dict):
        if not isinstance(data.get("cases"), list):
            raise DatasetLoadError(
                "Evaluation dataset object must contain a 'cases' "
                "array of evaluation cases."
            )
        data = data["cases"]

    if not isinstance(data, list):
        raise DatasetLoadError(
            "Evaluation dataset must contain a JSON array of "
            "evaluation cases, or an object with a 'cases' array."
        )

    if not isinstance(data, list):
        raise DatasetLoadError(
            "Evaluation dataset must contain a JSON array of "
            "evaluation cases."
        )

    cases: list[EvaluationCase] = []

    for index, item in enumerate(data):
        if not isinstance(item, dict):
            raise DatasetLoadError(
                f"Invalid evaluation case at index {index}: "
                "each case must be a JSON object."
            )

        try:
            case = EvaluationCase.model_validate(item)

        except ValidationError as exc:
            raise DatasetLoadError(
                f"Invalid evaluation case at index {index}: {exc}"
            ) from exc

        cases.append(case)

    if not cases:
        raise DatasetLoadError(
            f"Evaluation dataset is empty: {dataset_path}"
        )

    return cases