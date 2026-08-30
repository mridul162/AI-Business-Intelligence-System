"""Structured-output schema tests for the NL query parser."""

from __future__ import annotations

from dataclasses import dataclass, field

from etl.analytics.metrics.registry import list_metrics
from etl.analytics.nl_query.response_schema import build_response_schema
from etl.analytics.schemas import (
    KNOWN_COMPARISON_MODES,
    KNOWN_FILTER_OPERATORS,
    KNOWN_TIME_GRAINS,
)


@dataclass(frozen=True)
class FakeMetricDefinition:
    name: str
    supported_dimensions: tuple[str, ...] = field(default_factory=tuple)


def test_metric_enum_contains_exact_registry_metrics() -> None:
    schema = build_response_schema()
    expected = [definition.name for definition in list_metrics()]

    assert schema["properties"]["metric"]["enum"] == expected
    assert "total_investment" not in schema["properties"]["metric"]["enum"]


def test_additional_metrics_uses_same_canonical_metric_enum() -> None:
    schema = build_response_schema()

    assert (
        schema["properties"]["additional_metrics"]["items"]["enum"]
        == schema["properties"]["metric"]["enum"]
    )


def test_metric_enum_is_derived_from_supplied_registry_like_definitions() -> None:
    definitions = (
        FakeMetricDefinition("capital_invested"),
        FakeMetricDefinition("capital_withdrawn"),
        FakeMetricDefinition("total_payments"),
    )

    schema = build_response_schema(metric_definitions=definitions)

    assert schema["properties"]["metric"]["enum"] == [
        "capital_invested",
        "capital_withdrawn",
        "total_payments",
    ]
    assert "investment_amount" not in schema["properties"]["metric"]["enum"]


def test_registry_changes_are_reflected_without_manual_metric_list() -> None:
    original = (FakeMetricDefinition("capital_invested"),)
    changed = (
        FakeMetricDefinition("capital_invested"),
        FakeMetricDefinition("new_registry_metric"),
    )

    assert build_response_schema(metric_definitions=original)["properties"]["metric"][
        "enum"
    ] == ["capital_invested"]
    assert build_response_schema(metric_definitions=changed)["properties"]["metric"][
        "enum"
    ] == ["capital_invested", "new_registry_metric"]


def test_known_metric_regression_outputs_are_canonical_only() -> None:
    metric_enum = build_response_schema()["properties"]["metric"]["enum"]

    assert "capital_invested" in metric_enum
    assert "capital_withdrawn" in metric_enum
    assert "total_payments" in metric_enum

    assert "total_investment" not in metric_enum
    assert "owner_withdrawals" not in metric_enum
    assert "total_paid_amount" not in metric_enum


def test_other_finite_vocabularies_are_constrained() -> None:
    schema = build_response_schema(dimension_names=("customer_name", "product_category"))

    assert schema["properties"]["dimensions"]["items"]["enum"] == [
        "customer_name",
        "product_category",
    ]
    assert schema["properties"]["filters"]["items"]["properties"]["operator"]["enum"] == sorted(
        KNOWN_FILTER_OPERATORS
    )
    assert schema["properties"]["time_grain"]["anyOf"][0]["enum"] == sorted(
        KNOWN_TIME_GRAINS
    )
    assert schema["properties"]["comparison"]["anyOf"][0]["properties"]["mode"][
        "enum"
    ] == sorted(KNOWN_COMPARISON_MODES)
