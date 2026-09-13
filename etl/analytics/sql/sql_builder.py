"""
Turns ONE QueryPlan into a parameterized, not-yet-executed SQLAlchemy
Core statement. Does not execute SQL, does not handle MultiQueryPlan.

This module is responsible for orchestration and validation only;
the actual expression construction lives in clauses.py.
"""

from __future__ import annotations

from typing import Callable, Mapping, Optional

from sqlalchemy import select
from sqlalchemy.sql import Select

from etl.analytics.metrics.definitions import MetricDefinition
from etl.analytics.metrics.registry import get_metric as _default_get_metric
from etl.analytics.planner.query_plan import QueryPlan
from etl.analytics.query.time_grains import VIEW_PRIMARY_DATE_COLUMN

from . import clauses
from .errors import (
    InvalidLimitError,
    InvalidQueryPlanError,
    InvalidSortError,
    MissingTimeColumnError,
    SourceViewMismatchError,
    UnknownMetricError,
    UnsupportedDimensionError,
    UnsupportedFilterFieldError,
    UnsupportedFilterOperatorError,
    UnsupportedTimeGrainError,
)
from .sql_models import BuiltQuery

GetMetric = Callable[[str], MetricDefinition]

# --------------------------------------------------------------------
# ADAPTER NOTE: time column per source view
# --------------------------------------------------------------------
# Neither MetricDefinition nor QueryPlan names the timestamp/date
# column of a source_view. Fill this in with your real columns (or
# pass an override via `time_column_by_view=` to build_query) before
# running any plan that sets time_grain or time_range -- I've left it
# empty rather than guessing column names I can't verify against your
# schema, since a wrong guess would fail silently different (a real
# but wrong column) rather than loudly.
TIME_COLUMN_BY_SOURCE_VIEW: dict[str, str] = dict(VIEW_PRIMARY_DATE_COLUMN)

TIME_BUCKET_ALIAS = "period"


def build_query(
    plan: QueryPlan,
    *,
    get_metric: GetMetric = _default_get_metric,
    time_column_by_view: Optional[Mapping[str, str]] = None,
) -> BuiltQuery:
    """
    Validate `plan` and compile it into a BuiltQuery.

    Raises one of the exceptions in errors.py on any invalid input;
    never raises a bare KeyError/AttributeError/etc. for expected
    failure modes.
    """
    time_columns = time_column_by_view or TIME_COLUMN_BY_SOURCE_VIEW

    metric_defs = _resolve_metrics(plan, get_metric)
    _validate_source_view(plan, metric_defs)
    _validate_output_fields_unique(metric_defs)

    dimensions = _validate_dimensions(plan, metric_defs)
    time_grain = _validate_time_grain(plan, metric_defs)

    time_column = None
    if time_grain is not None or plan.time_range is not None:
        time_column = _resolve_time_column(plan.source_view, time_columns)

    table = clauses.source_table(plan.source_view)

    select_columns = [clauses.metric_column(md) for md in metric_defs]
    select_columns += [clauses.dimension_column(d) for d in dimensions]

    group_by_exprs = list(select_columns[len(metric_defs):])  # dimension cols

    time_bucket_alias = None
    if time_grain is not None:
        bucket_expr = clauses.time_bucket_expr(time_column, time_grain) # type: ignore
        select_columns.append(bucket_expr.label(TIME_BUCKET_ALIAS))
        group_by_exprs.append(bucket_expr)
        time_bucket_alias = TIME_BUCKET_ALIAS

    where_clauses = clauses.fixed_filter_clauses(metric_defs)
    where_clauses += _validate_and_build_user_filters(plan, metric_defs)
    if plan.time_range is not None:
        where_clauses += clauses.time_range_clauses(time_column, plan.time_range) # type: ignore

    stmt: Select = select(*select_columns).select_from(table)

    where = clauses.combine_where(where_clauses)
    if where is not None:
        stmt = stmt.where(where)

    if group_by_exprs:
        stmt = stmt.group_by(*group_by_exprs)

    if plan.sort_by is not None:
        stmt = stmt.order_by(
            _validate_and_build_sort(plan, metric_defs, dimensions, time_bucket_alias)
        )

    if plan.limit is not None:
        stmt = stmt.limit(_validate_limit(plan.limit))

    return BuiltQuery(
        statement=stmt,
        plan=plan,
        metric_output_fields=tuple(md.output_field for md in metric_defs),
        dimension_fields=tuple(dimensions),
        time_bucket_alias=time_bucket_alias,
    )


# --------------------------------------------------------------------
# Validation steps
# --------------------------------------------------------------------


def _resolve_metrics(
    plan: QueryPlan, get_metric: GetMetric
) -> list[MetricDefinition]:
    if not plan.metrics:
        # Defensive: QueryPlan.__post_init__ already prevents this.
        raise InvalidQueryPlanError("QueryPlan has no metrics.")

    resolved = []
    for name in plan.metrics:
        try:
            resolved.append(get_metric(name))
        except KeyError as exc:
            raise UnknownMetricError(f"Unknown metric: {name!r}") from exc
    return resolved


def _validate_source_view(
    plan: QueryPlan, metric_defs: list[MetricDefinition]
) -> None:
    for md in metric_defs:
        if md.source_view != plan.source_view:
            raise SourceViewMismatchError(
                f"Metric {md.name!r} belongs to source_view "
                f"{md.source_view!r}, but QueryPlan.source_view is "
                f"{plan.source_view!r}."
            )


def _validate_output_fields_unique(metric_defs: list[MetricDefinition]) -> None:
    seen: set[str] = set()
    for md in metric_defs:
        if md.output_field in seen:
            raise InvalidQueryPlanError(
                f"Two metrics in this plan both produce output_field "
                f"{md.output_field!r}, which would collide in the "
                f"SELECT list."
            )
        seen.add(md.output_field)


def _validate_dimensions(
    plan: QueryPlan, metric_defs: list[MetricDefinition]
) -> tuple[str, ...]:
    for dim in plan.dimensions:
        for md in metric_defs:
            if dim not in md.supported_dimensions:
                raise UnsupportedDimensionError(
                    f"Dimension {dim!r} is not supported by metric "
                    f"{md.name!r}."
                )
    return plan.dimensions


def _validate_time_grain(
    plan: QueryPlan, metric_defs: list[MetricDefinition]
) -> Optional[str]:
    if plan.time_grain is None:
        return None
    for md in metric_defs:
        if plan.time_grain not in md.supported_time_grains:
            raise UnsupportedTimeGrainError(
                f"Time grain {plan.time_grain!r} is not supported by "
                f"metric {md.name!r}."
            )
    if plan.time_grain not in clauses.TIME_GRAIN_TO_DATE_TRUNC:
        raise UnsupportedTimeGrainError(
            f"No DATE_TRUNC mapping for time grain {plan.time_grain!r}."
        )
    return plan.time_grain


def _resolve_time_column(
    source_view: str, time_columns: Mapping[str, str]
) -> str:
    try:
        return time_columns[source_view]
    except KeyError as exc:
        raise MissingTimeColumnError(
            f"No time column configured for source_view "
            f"{source_view!r}. Add it to TIME_COLUMN_BY_SOURCE_VIEW "
            f"or pass time_column_by_view= to build_query()."
        ) from exc


def _validate_and_build_user_filters(
    plan: QueryPlan, metric_defs: list[MetricDefinition]
) -> list:
    built = []
    for pf in plan.filters:
        for md in metric_defs:
            if pf.field not in md.supported_dimensions:
                raise UnsupportedFilterFieldError(
                    f"Filter field {pf.field!r} is not supported by "
                    f"metric {md.name!r}."
                )
        if pf.operator not in clauses.FILTER_OPERATORS:
            raise UnsupportedFilterOperatorError(
                f"Unsupported filter operator: {pf.operator!r}"
            )
        built.append(clauses.user_filter_clause(pf))
    return built


def _validate_and_build_sort(
    plan: QueryPlan,
    metric_defs: list[MetricDefinition],
    dimensions: tuple[str, ...],
    time_bucket_alias: Optional[str],
):
    allowed = {md.output_field for md in metric_defs}
    allowed.update(dimensions)
    if time_bucket_alias is not None:
        allowed.add(time_bucket_alias)

    if plan.sort_by not in allowed:
        raise InvalidSortError(
            f"sort_by {plan.sort_by!r} is not one of the selected "
            f"columns: {sorted(allowed)!r}."
        )

    from sqlalchemy import column as _column

    sort_col = _column(plan.sort_by)
    order = (plan.sort_order or "asc").lower()
    if order == "desc":
        return sort_col.desc()
    if order == "asc":
        return sort_col.asc()
    raise InvalidSortError(
        f"sort_order must be 'asc' or 'desc', got {plan.sort_order!r}."
    )


def _validate_limit(limit: int) -> int:
    if not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0:
        raise InvalidLimitError(
            f"limit must be a positive integer, got {limit!r}."
        )
    return limit