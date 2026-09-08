"""
Turns a resolved AnalyticalQueryRequest into a QueryPlanResult.

This module is REGISTRY-DRIVEN: it never special-cases specific
metric names (no `if "total_sales" in metrics`). All grouping
decisions come from looking up each metric's MetricDefinition in the
metric registry and comparing `source_view` / `fixed_filters`.

--------------------------------------------------------------------
ADAPTER NOTE -- read this before wiring into the real project
--------------------------------------------------------------------
I don't have your actual metric registry module, so the three types
below (`RegistryFilter`, `MetricDefinition`, `MetricRegistry`) are a
minimal Protocol/interface inferred from the review discussion, not
your real classes. Two ways to connect this to your codebase:

  1. If your registry's metric objects already expose `.source_view`
     and an iterable `.fixed_filters` of objects with
     `.field` / `.operator` / `.value`, you can delete the stub
     classes below and just change the `resolve_metric` import to
     point at your real registry lookup function. Nothing else in
     `plan_query` needs to change.
  2. Otherwise, write a small adapter function that maps your real
     metric definition to this shape and pass it in as
     `resolve_metric`.

The request type (`AnalyticalQueryRequest`) is handled the same way:
`plan_query` only ever reads `.metrics`, `.dimensions`, `.filters`,
`.time_range`, `.time_grain`, `.sort_by`, `.sort_order`, `.limit`,
and an optional `.comparison` flag (see MergeStrategy selection
below) via getattr, so any object with those attributes works.
--------------------------------------------------------------------
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable, Optional, Protocol

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


# --------------------------------------------------------------------
# Registry interface (see ADAPTER NOTE above)
# --------------------------------------------------------------------


@dataclass(frozen=True)
class RegistryFilter:
    """A metric's own always-on filter, e.g. direction = 'IN'."""

    field: str
    operator: str
    value: Any


@dataclass(frozen=True)
class MetricDefinition:
    """Minimal shape this planner needs from a registry metric."""

    name: str
    source_view: str
    fixed_filters: tuple[RegistryFilter, ...] = ()


class MetricRegistry(Protocol):
    def get_metric(self, name: str) -> MetricDefinition:
        ...


class UnknownMetricError(KeyError):
    """Raised when a requested metric name isn't in the registry."""


# --------------------------------------------------------------------
# Errors
# --------------------------------------------------------------------


class ConflictingFixedFiltersError(ValueError):
    """
    Raised when two metrics that were forced together (e.g. by an
    explicit comparison request) share a source_view but have fixed
    filters that directly conflict, and the caller has no way to
    split them (this shouldn't happen in normal planning -- planning
    always splits conflicting metrics into separate QueryPlans -- but
    is kept as a defensive check).
    """


# --------------------------------------------------------------------
# Internal helpers
# --------------------------------------------------------------------


def _filters_compatible(
    a: tuple[RegistryFilter, ...], b: tuple[RegistryFilter, ...]
) -> bool:
    """
    Two fixed-filter sets are compatible if no field appears in both
    with a different value. Compatible sets can be merged into one
    QueryPlan (their union becomes that plan's fixed filters);
    incompatible sets force separate QueryPlans.
    """
    a_by_field = {f.field: (f.operator, f.value) for f in a}
    for f in b:
        existing = a_by_field.get(f.field)
        if existing is not None and existing != (f.operator, f.value):
            return False
    return True


def _merge_filters(
    a: tuple[RegistryFilter, ...], b: tuple[RegistryFilter, ...]
) -> tuple[RegistryFilter, ...]:
    """Union two compatible fixed-filter sets, deduplicating by field."""
    merged: dict[str, RegistryFilter] = {f.field: f for f in a}
    for f in b:
        merged.setdefault(f.field, f)
    return tuple(merged.values())


@dataclass
class _Group:
    """One in-progress cluster of metrics destined for one QueryPlan."""

    source_view: str
    metric_names: list[str]
    fixed_filters: tuple[RegistryFilter, ...]


def _group_metrics(
    definitions: list[MetricDefinition],
) -> list[_Group]:
    """
    Cluster resolved metric definitions into groups that can share one
    QueryPlan: same source_view, and pairwise-compatible fixed
    filters. Greedy: within a source_view, add each metric to the
    first existing group whose merged fixed filters remain compatible;
    otherwise start a new group.
    """
    groups: list[_Group] = []

    for md in definitions:
        placed = False
        for g in groups:
            if g.source_view != md.source_view:
                continue
            if _filters_compatible(g.fixed_filters, md.fixed_filters):
                g.metric_names.append(md.name)
                g.fixed_filters = _merge_filters(
                    g.fixed_filters, md.fixed_filters
                )
                placed = True
                break
        if not placed:
            groups.append(
                _Group(
                    source_view=md.source_view,
                    metric_names=[md.name],
                    fixed_filters=md.fixed_filters,
                )
            )

    return groups


def _choose_merge_strategy(
    groups: list[_Group], request: Any
) -> MergeStrategy:
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


def _build_query_plan(
    group: _Group, request: Any
) -> QueryPlan:
    """
    Build one QueryPlan from a metric group plus the shared
    request-level dimensions/filters/time/sort/limit.

    Request-level filters (user-requested) and the group's merged
    fixed filters (registry-derived) are combined here -- see
    PlanFilter's docstring for why QueryPlan doesn't track which is
    which past this point.
    """
    user_filters = tuple(
        PlanFilter(field=f.field, operator=f.operator, value=f.value)
        for f in getattr(request, "filters", ()) or ()
    )
    fixed_filters = tuple(
        PlanFilter(field=f.field, operator=f.operator, value=f.value)
        for f in group.fixed_filters
    )

    return QueryPlan(
        source_view=group.source_view,
        metrics=tuple(group.metric_names),
        dimensions=tuple(getattr(request, "dimensions", ()) or ()),
        filters=user_filters + fixed_filters,
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
            returns its MetricDefinition. Raise UnknownMetricError
            (or let a KeyError propagate) for an unknown name.

    Returns:
        A bare QueryPlan if all requested metrics can share one SQL
        query, otherwise a MultiQueryPlan with an appropriate
        MergeStrategy.
    """
    metric_names: Iterable[str] = getattr(request, "metrics")
    if not metric_names:
        raise ValueError("plan_query requires at least one metric.")

    definitions = [resolve_metric(name) for name in metric_names]

    groups = _group_metrics(definitions)

    plans = [_build_query_plan(g, request) for g in groups]

    if len(plans) == 1:
        return plans[0]

    merge_strategy = _choose_merge_strategy(groups, request)
    return MultiQueryPlan(plans=tuple(plans), merge_strategy=merge_strategy)