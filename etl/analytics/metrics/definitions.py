"""
Machine-readable definitions for BI metrics.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


TimeGrain = Literal[
    "daily",
    "weekly",
    "monthly",
    "quarterly",
    "yearly",
]

AggregationType = Literal[
    "sum",
    "count",
    "count_distinct",
    "average",
    "ratio",
]


@dataclass(frozen=True)
class MetricDefinition:
    """
    Defines one business metric.

    This class contains metadata only. It does not execute SQL.
    """

    name: str
    display_name: str
    description: str

    source_view: str
    aggregation: AggregationType
    expression: str

    filters: tuple[str, ...]

    supported_dimensions: tuple[str, ...]
    supported_time_grains: tuple[TimeGrain, ...]

    output_field: str

    zero_if_no_data: bool = True
    null_if_denominator_zero: bool = False