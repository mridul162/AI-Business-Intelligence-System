# etl/analytics/nl_query/schemas.py

from __future__ import annotations

from typing import Sequence


def build_parser_json_schema(
    metric_names: Sequence[str],
    dimension_names: Sequence[str],
) -> dict:
    """Build the JSON schema used to constrain LLM output."""

    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "metric": {
                "type": "string",
                "enum": list(metric_names),
            },
            "additional_metrics": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": list(metric_names),
                },
            },
            "dimensions": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": list(dimension_names),
                },
            },
            "filters": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "dimension": {
                            "type": "string",
                            "enum": list(dimension_names),
                        },
                        "operator": {
                            "type": "string",
                            "enum": [
                                "=",
                                "!=",
                                ">",
                                ">=",
                                "<",
                                "<=",
                            ],
                        },
                        "value": {},
                    },
                    "required": [
                        "dimension",
                        "operator",
                        "value",
                    ],
                },
            },
            "time_grain": {
                "type": ["string", "null"],
                "enum": [
                    *dimension_names[:0],  # no-op; remove this
                ],
            },
            "time_range": {
                "type": ["object", "null"],
                "additionalProperties": False,
                "properties": {
                    "preset": {
                        "type": ["string", "null"],
                    },
                    "label": {
                        "type": ["string", "null"],
                    },
                    "start": {
                        "type": ["string", "null"],
                    },
                    "end": {
                        "type": ["string", "null"],
                    },
                },
                "required": [
                    "preset",
                    "label",
                    "start",
                    "end",
                ],
            },
            "limit": {
                "type": ["integer", "null"],
            },
            "sort_by": {
                "type": ["string", "null"],
            },
            "sort_order": {
                "type": ["string", "null"],
                "enum": ["asc", "desc", None],
            },
            "comparison": {
                "type": ["object", "null"],
                "additionalProperties": False,
                "properties": {
                    "mode": {
                        "type": "string",
                    },
                },
                "required": ["mode"],
            },
        },
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
    }