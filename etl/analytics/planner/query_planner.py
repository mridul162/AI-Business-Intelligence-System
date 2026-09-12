"""
Turns a resolved AnalyticalQueryRequest into a QueryPlanResult.

This module is REGISTRY-DRIVEN: it never special-cases specific
metric names (no `if "total_sales" in metrics`). All grouping
decisions come from looking up each metric's MetricDefinition in the
metric registry and comparing `source_view` / `filters`.

--------------------------------------------------------------------
CONTRACT NOTE -- fixed filters are NOT merged into QueryPlan.filters
--------------------------------------------------------------------
etl.analytics.metrics.definitions.MetricDefinition.filters holds
trusted, registry-authored raw SQL fragments (e.g. "direction = 'IN'"),
not structured field/operator/value objects. This planner cannot (and
should not try to) parse those strings -- see the SQL Builder's
clauses.fixed_filter_clauses(), which independently re-fetches each
plan metric's MetricDefinition.filters straight from the registry via
get_metric() and applies them as trusted text() clauses at build time.

So: QueryPlan.filters here holds ONLY user-requested filters (from
the request). Grouping still respects fixed filters -- two metrics
that share a source_view but have different `filters` tuples (e.g.
cash_in's "direction = 'IN'" vs cash_out's "direction = 'OUT'") are
still put in separate QueryPlans, via exact-set comparison of the raw
filter strings (see _group_metrics). This is a conservative rule: it
correctly separates metrics with genuinely conflicting fixed filters,
but it will also separate two metrics whose fixed filters happen to
differ without truly conflicting (e.g. two unrelated single-field
filters on different columns) into different QueryPlans even though a
smarter parser could have combined them. That's a correctness-over-
cleverness tradeoff given the registry doesn't expose structured
filter metadata.

The request type (`AnalyticalQueryRequest`) is duck-typed: plan_query
only ever reads `.metrics`, `.dimensions`, `.filters`, `.time_range`,
`.time_grain`, `.sort_by`, `.sort_order`, `.limit`, and an optional
`.comparison` flag (see MergeStrategy selection below) via getattr,
so any object with those attributes works.
--------------------------------------------------------------------
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

from etl.analytics.metrics.definitions import MetricDefinition

try:
    from .query_plan import (
        MergeStrategy,
        MultiQueryPlan,
        PlanFilter,
        QueryPlan,
        QueryPlanResult,
    )
except ImportError:  # pragma: no cover - fallback for standalone/script use
    from query_plan import (
        MergeStrategy,
        MultiQueryPlan,
        PlanFilter,
        QueryPlan,
        QueryPlanResult,
    )


class UnknownMetricError(KeyError):
    """Raised when a requested metric name isn't in the registry."""


# --------------------------------------------------------------------
# Internal helpers
# --------------------------------------------------------------------


@dataclass
class _Group:
    """One cluster of metrics destined for one QueryPlan."""

    source_view: str
    fixed_filters: frozenset[str]
    metric_names: list[str] = field(default_factory=list)


def _group_metrics(definitions: list[MetricDefinition]) -> list[_Group]:
    """
    Cluster resolved metric definitions into groups that can share one
    QueryPlan: same source_view AND an identical set of registry fixed
    filters. Order-preserving (first-seen group order), so plan order
    is deterministic for a given request.
    """
    groups_by_key: dict[tuple[str, frozenset[str]], _Group] = {}
    ordered_keys: list[tuple[str, frozenset[str]]] = []

    for md in definitions:
        key = (md.source_view, frozenset(md.filters))
        group = groups_by_key.get(key)
        if group is None:
            group = _Group(source_view=md.source_view, fixed_filters=key[1])
            groups_by_key[key] = group
            ordered_keys.append(key)
        group.metric_names.append(md.name)

    return [groups_by_key[key] for key in ordered_keys]


def _choose_merge_strategy(groups: list[_Group], request: Any) -> MergeStrategy:
    """
    Decide how multiple QueryPlans should be merged.

    - All groups share one source_view -> the split was purely
      structural (fixed-filter conflict): SPLIT_METRICS.
    - Groups span different source_views and the request explicitly
      framed this as a comparison: COMPARE_METRICS.
    - Otherwise (different source_views, no comparison framing):
      SIDE_BY_SIDE.
    """
    source_views = {g.source_view for g in groups}

    if len(source_views) == 1:
        return MergeStrategy.SPLIT_METRICS

    if getattr(request, "comparison", False):
        return MergeStrategy.COMPARE_METRICS

    return MergeStrategy.SIDE_BY_SIDE


def _build_query_plan(group: _Group, request: Any) -> QueryPlan:
    """
    Build one QueryPlan from a metric group plus the shared
    request-level dimensions/filters/time/sort/limit.

    QueryPlan.filters holds ONLY the user-requested filters -- see
    module docstring for why registry fixed filters are deliberately
    left out here and applied later by the SQL Builder instead.
    """
    user_filters: tuple[PlanFilter, ...] = tuple(getattr(request, "filters", ()) or ())

    return QueryPlan(
        source_view=group.source_view,
        metrics=tuple(group.metric_names),
        dimensions=tuple(getattr(request, "dimensions", ()) or ()),
        filters=user_filters,
        time_range=getattr(request, "time_range", None),
        time_grain=getattr(request, "time_grain", None),
        sort_by=getattr(request, "sort_by", None),
        sort_order=getattr(request, "sort_order", None),
        limit=getattr(request, "limit", None),
    )


# --------------------------------------------------------------------
# Public entry point
# --------------------------------------------------------------------


def plan_query(
    request: Any,
    resolve_metric: Callable[[str], MetricDefinition],
) -> QueryPlanResult:
    """
    Build a QueryPlanResult for `request`.

    Args:
        request: the resolved analytical query request. Must expose
            `.metrics` (iterable of metric name strings) and may
            expose `.dimensions`, `.filters`, `.time_range`,
            `.time_grain`, `.sort_by`, `.sort_order`, `.limit`, and
            `.comparison` (bool, defaults to False if absent).
        resolve_metric: looks up a metric name in the registry and
            returns its MetricDefinition (e.g.
            etl.analytics.metrics.registry.get_metric). A KeyError
            for an unknown name is re-raised as UnknownMetricError.

    Returns:
        A bare QueryPlan if all requested metrics can share one SQL
        query, otherwise a MultiQueryPlan with an appropriate
        MergeStrategy.
    """
    metric_names: Iterable[str] = getattr(request, "metrics")
    if not metric_names:
        raise ValueError("plan_query requires at least one metric.")

    definitions = []
    for name in metric_names:
        try:
            definitions.append(resolve_metric(name))
        except KeyError as exc:
            raise UnknownMetricError(f"Unknown metric: {name!r}") from exc

    groups = _group_metrics(definitions)

    plans = [_build_query_plan(g, request) for g in groups]

    if len(plans) == 1:
        return plans[0]

    merge_strategy = _choose_merge_strategy(groups, request)
    return MultiQueryPlan(plans=tuple(plans), merge_strategy=merge_strategy)