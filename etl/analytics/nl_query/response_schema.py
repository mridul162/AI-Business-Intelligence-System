"""
Structured-output JSON Schema for natural-language analytical queries.

The metric registry is the source of truth for metric identifiers. This
module only translates registry/configuration metadata into a JSON Schema;
it does not call an LLM, resolve semantics, build SQL, or execute queries.
"""

from __future__ import annotations

from typing import Any, Iterable, Sequence

from etl.analytics.metrics.registry import list_metrics
from etl.analytics.schemas import (
    KNOWN_COMPARISON_MODES,
    KNOWN_FILTER_OPERATORS,
    KNOWN_PRESETS,
    KNOWN_TIME_GRAINS,
)


def _sorted_unique(values: Iterable[str]) -> list[str]:
    return sorted(set(values))


def canonical_metric_names(metric_definitions: Sequence[object] | None = None) -> tuple[str, ...]:
    """Return canonical metric names from registry-style definitions."""

    definitions = metric_definitions if metric_definitions is not None else list_metrics()
    return tuple(definition.name for definition in definitions)  # type: ignore[attr-defined]


def canonical_dimension_names(metric_definitions: Sequence[object] | None = None) -> tuple[str, ...]:
    """Return known dimension names declared by the metric registry."""

    definitions = metric_definitions if metric_definitions is not None else list_metrics()
    return tuple(
        _sorted_unique(
            dimension
            for definition in definitions
            for dimension in definition.supported_dimensions  # type: ignore[attr-defined]
        )
    )


def _nullable(schema: dict[str, Any]) -> dict[str, Any]:
    return {"anyOf": [schema, {"type": "null"}]}


def build_response_schema(
    *,
    metric_definitions: Sequence[object] | None = None,
    dimension_names: Sequence[str] | None = None,
) -> dict[str, Any]:
    """
    Build the strict JSON Schema consumed by completion providers.

    Metric enums are generated from the metric registry, never from a
    duplicated allowlist. Dimension enums are generated from the
    registry's declared supported dimensions unless an explicit
    provider-independent dimension vocabulary is supplied.
    """

    metric_names = list(canonical_metric_names(metric_definitions))
    dimensions = (
        _sorted_unique(dimension_names)
        if dimension_names is not None
        else list(canonical_dimension_names(metric_definitions))
    )

    dimension_schema: dict[str, Any] = {"type": "string"}
    if dimensions:
        dimension_schema["enum"] = dimensions

    metric_schema: dict[str, Any] = {
        "type": "string",
        "enum": metric_names,
    }

    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "metric",
            "additional_metrics",
            "dimensions",
            "filters",
            "time_grain",
            "time_range",
            "limit",
            "sort_by",
            "sort_order",
            "comparison",
        ],
        "properties": {
            "metric": metric_schema,
            "additional_metrics": {
                "type": "array",
                "items": metric_schema,
            },
            "dimensions": {
                "type": "array",
                "items": dimension_schema,
            },
            "filters": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["dimension", "operator", "value"],
                    "properties": {
                        "dimension": dimension_schema,
                        "operator": {
                            "type": "string",
                            "enum": sorted(KNOWN_FILTER_OPERATORS),
                        },
                        "value": {
                            "anyOf": [
                                {"type": "string"},
                                {"type": "number"},
                                {"type": "boolean"},
                                {"type": "array", "items": {"type": "string"}},
                                {"type": "array", "items": {"type": "number"}},
                                {"type": "null"},
                            ],
                        },
                    },
                },
            },
            "time_grain": _nullable(
                {
                    "type": "string",
                    "enum": sorted(KNOWN_TIME_GRAINS),
                }
            ),
            "time_range": _nullable(
                {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["preset", "label", "start", "end"],
                    "properties": {
                        "preset": _nullable(
                            {
                                "type": "string",
                                "enum": sorted(KNOWN_PRESETS),
                            }
                        ),
                        "label": _nullable({"type": "string"}),
                        "start": _nullable({"type": "string"}),
                        "end": _nullable({"type": "string"}),
                    },
                }
            ),
            "limit": _nullable({"type": "integer", "minimum": 1}),
            "sort_by": _nullable({"type": "string"}),
            "sort_order": _nullable({"type": "string", "enum": ["asc", "desc"]}),
            "comparison": _nullable(
                {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["mode"],
                    "properties": {
                        "mode": {
                            "type": "string",
                            "enum": sorted(KNOWN_COMPARISON_MODES),
                        },
                    },
                }
            ),
        },
    }
