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

    # Business-language terms that should resolve to this metric via
    # etl.analytics.semantic.metric_resolver.resolve_metric, in
    # addition to the metric's own `name` and `display_name` (both of
    # which are always matched and don't need to be repeated here).
    # More than one metric may legitimately claim the same alias
    # (e.g. "earnings") -- resolve_metric treats that as genuine
    # ambiguity to surface to the user, not something to guess past.
    aliases: tuple[str, ...] = ()