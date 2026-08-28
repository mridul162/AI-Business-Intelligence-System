from __future__ import annotations

import json

import pytest

from evaluation.loaders.dataset_loader import (
    DatasetLoadError,
    load_evaluation_dataset,
)
from evaluation.schemas.evaluation_case import EvaluationCase


def _valid_case() -> dict:
    return {
        "id": "eval_001",
        "question": "What are our net sales?",
        "category": "direct_metric",
        "difficulty": "easy",
        "expected_status": "success",
        "expected_metrics": ["net_sales"],
        "expected_dimensions": [],
        "expected_filters": [],
        "expected_time_grain": None,
    }


def _write_json(path, data) -> None:
    path.write_text(
        json.dumps(data),
        encoding="utf-8",
    )


# -------------------------------------------------------------------
# Successful loading
# -------------------------------------------------------------------


def test_load_evaluation_dataset_returns_validated_cases(
    tmp_path,
) -> None:
    dataset_path = tmp_path / "analytics_eval_v1.json"

    _write_json(
        dataset_path,
        [
            _valid_case(),
            {
                "id": "eval_002",
                "question": "Show net sales by month.",
                "category": "time_based",
                "difficulty": "easy",
                "expected_status": "success",
                "expected_metrics": ["net_sales"],
                "expected_dimensions": [],
                "expected_filters": [],
                "expected_time_grain": "monthly",
            },
        ],
    )

    cases = load_evaluation_dataset(dataset_path)

    assert len(cases) == 2
    assert all(isinstance(case, EvaluationCase) for case in cases)
    assert cases[0].id == "eval_001"
    assert cases[1].id == "eval_002"


# -------------------------------------------------------------------
# Missing file
# -------------------------------------------------------------------


def test_load_evaluation_dataset_raises_for_missing_file(
    tmp_path,
) -> None:
    dataset_path = tmp_path / "does_not_exist.json"

    with pytest.raises(
        DatasetLoadError,
        match="does not exist",
    ):
        load_evaluation_dataset(dataset_path)


# -------------------------------------------------------------------
# Path is not a file
# -------------------------------------------------------------------


def test_load_evaluation_dataset_raises_when_path_is_directory(
    tmp_path,
) -> None:
    with pytest.raises(
        DatasetLoadError,
        match="is not a file",
    ):
        load_evaluation_dataset(tmp_path)


# -------------------------------------------------------------------
# Invalid JSON
# -------------------------------------------------------------------


def test_load_evaluation_dataset_raises_for_invalid_json(
    tmp_path,
) -> None:
    dataset_path = tmp_path / "invalid.json"

    dataset_path.write_text(
        '{"id": "eval_001",',
        encoding="utf-8",
    )

    with pytest.raises(
        DatasetLoadError,
        match="Invalid JSON",
    ):
        load_evaluation_dataset(dataset_path)


# -------------------------------------------------------------------
# Invalid top-level structure
# -------------------------------------------------------------------


def test_load_evaluation_dataset_raises_when_dataset_object_has_no_cases(
    tmp_path,
) -> None:
    dataset_path = tmp_path / "analytics_eval_v1.json"

    _write_json(
        dataset_path,
        _valid_case(),
    )

    with pytest.raises(
        DatasetLoadError,
        match="must contain a 'cases' array",
    ):
        load_evaluation_dataset(dataset_path)


# -------------------------------------------------------------------
# Non-object item inside array
# -------------------------------------------------------------------


@pytest.mark.parametrize(
    "invalid_item",
    [
        "not an object",
        123,
        [],
        None,
    ],
)
def test_load_evaluation_dataset_raises_for_non_object_case(
    tmp_path,
    invalid_item,
) -> None:
    dataset_path = tmp_path / "analytics_eval_v1.json"

    _write_json(
        dataset_path,
        [invalid_item],
    )

    with pytest.raises(
        DatasetLoadError,
        match="each case must be a JSON object",
    ):
        load_evaluation_dataset(dataset_path)


# -------------------------------------------------------------------
# Schema validation failure
# -------------------------------------------------------------------


def test_load_evaluation_dataset_raises_for_invalid_case(
    tmp_path,
) -> None:
    dataset_path = tmp_path / "analytics_eval_v1.json"

    invalid_case = _valid_case()
    invalid_case.pop("question")

    _write_json(
        dataset_path,
        [invalid_case],
    )

    with pytest.raises(
        DatasetLoadError,
        match="Invalid evaluation case at index 0",
    ):
        load_evaluation_dataset(dataset_path)


# -------------------------------------------------------------------
# Empty dataset
# -------------------------------------------------------------------


def test_load_evaluation_dataset_raises_for_empty_dataset(
    tmp_path,
) -> None:
    dataset_path = tmp_path / "empty.json"

    _write_json(
        dataset_path,
        [],
    )

    with pytest.raises(
        DatasetLoadError,
        match="dataset is empty",
    ):
        load_evaluation_dataset(dataset_path)