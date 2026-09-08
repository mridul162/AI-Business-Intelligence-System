"""
Data model for query plans produced by the query planner.

This module defines ONLY data. It does not decide how metrics get
grouped into plans (that's query_planner.py) and it does not generate
SQL (that's the sql/ package, Milestone 2).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class MergeStrategy(str, Enum):
    """
    How multiple QueryPlans in a MultiQueryPlan should be combined
    into one AnalyticalQueryResponse.

    NONE:
        Not used on a MultiQueryPlan itself -- a single-source request
        is represented as a bare QueryPlan, not a MultiQueryPlan. This
        member exists so callers have an explicit value to reach for
        when describing "no merge occurred" (e.g. logging, tests)
        without inventing a sentinel.

    COMPARE_METRICS:
        Two or more metrics from different sources, explicitly framed
        by the user as a comparison (e.g. "Compare total sales and
        total expenses"). Rows are aligned by time/dimension and each
        metric becomes its own column.

    SPLIT_METRICS:
        Two or more metrics that share the same source_view but
        cannot be expressed as one SQL query because their registry
        fixed_filters conflict -- e.g. cash_in (direction = 'IN')
        and cash_out (direction = 'OUT') both read
        analytics.v_cash_transactions. The split is driven by a
        structural (schema) reason rather than user phrasing, but the
        merge shape is identical to COMPARE_METRICS: rows aligned by
        time/dimension, each metric its own column. Kept as a
        separate value (rather than folded into COMPARE_METRICS) so
        the merger and any logging/debugging can tell *why* the
        metrics were split.

    SIDE_BY_SIDE:
        Two or more unrelated metrics from different sources, listed
        together without an explicit comparison framing (e.g. "Show
        orders and total payments"). Presented together but without
        implying a comparative relationship.
    """

    NONE = "none"
    COMPARE_METRICS = "compare_metrics"
    SPLIT_METRICS = "split_metrics"
    SIDE_BY_SIDE = "side_by_side"


@dataclass(frozen=True)
class PlanFilter:
    """
    One filter clause attached to a QueryPlan.

    Mirrors the `field` / `operator` / `value` shape used throughout
    the NL parser and semantic resolver (see prompts.py and the eval
    dataset) -- deliberately NOT called `dimension`, since a filter
    field may be a filterable-but-not-groupable column such as
    `amount`.

    A QueryPlan's `filters` tuple may contain a mix of user-requested
    filters (from AnalyticalQueryRequest) and metric fixed filters
    (from the metric registry, e.g. direction = 'IN' for cash_in).
    QueryPlan does not track which is which -- by the time filters
    land here they're just WHERE-clause conditions to the SQL
    builder. query_planner.py is responsible for using the
    *provenance* of fixed filters (before they're merged in) to
    decide whether metrics can share a QueryPlan in the first place;
    see MetricDefinition.fixed_filters.
    """

    field: str
    operator: str
    value: Any


@dataclass(frozen=True)
class QueryPlan:
    """
    A single executable unit of analytical intent: one source view,
    one or more metrics that can legally share one SQL query against
    that view, and the grouping/filtering/sorting to apply.

    All metrics in `metrics` MUST:
      - share the same `source_view`
      - share the same fixed registry `filters` (the metric's own
        always-on conditions, e.g. direction = 'IN' for cash_in) --
        metrics with conflicting fixed filters cannot be combined
        into one QueryPlan even if they share a source_view.
    query_planner.py is responsible for enforcing this; QueryPlan
    itself only enforces that it isn't empty.
    """

    source_view: str
    metrics: tuple[str, ...]
    dimensions: tuple[str, ...] = field(default_factory=tuple)
    filters: tuple[PlanFilter, ...] = field(default_factory=tuple)
    time_range: Optional[Any] = None
    time_grain: Optional[str] = None
    sort_by: Optional[str] = None
    sort_order: Optional[str] = None
    limit: Optional[int] = None

    def __post_init__(self) -> None:
        if not self.metrics:
            raise ValueError(
                "QueryPlan requires at least one metric."
            )

        if not self.source_view:
            raise ValueError(
                "QueryPlan requires a non-empty source_view."
            )


@dataclass(frozen=True)
class MultiQueryPlan:
    """
    Two or more QueryPlans that must be executed independently and
    then merged (Milestone 4) because their metrics cannot share one
    SQL query.
    """

    plans: tuple[QueryPlan, ...]
    merge_strategy: MergeStrategy

    def __post_init__(self) -> None:
        if len(self.plans) < 2:
            raise ValueError(
                "MultiQueryPlan requires at least two QueryPlans; "
                "a single-source request should be a bare QueryPlan."
            )

        if self.merge_strategy is MergeStrategy.NONE:
            raise ValueError(
                "MultiQueryPlan cannot use MergeStrategy.NONE -- "
                "that value is reserved for describing a bare "
                "QueryPlan (no merge occurred)."
            )


# The planner's return type: either one plan (single source) or
# several plans plus instructions for combining them.
QueryPlanResult = QueryPlan | MultiQueryPlan