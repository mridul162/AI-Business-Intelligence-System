"""
Deterministic construction of SQLAlchemy Core expressions.

Nothing in this module makes a decision about *whether* a given
dimension/filter/grain is allowed for a given plan -- that's
validation, and it lives in sql_builder.py. This module only knows
how to turn an already-validated piece of a QueryPlan into a
SQLAlchemy expression.

Trust boundary (read this before touching filters):

  - MetricDefinition.expression and MetricDefinition.filters come
    from the metric registry -- a file developers edit, not user
    input. They are inserted as raw SQL via literal_column()/text().
    This is safe *only* because these strings are trusted, not
    because literal_column/text are inherently safe -- never route
    user-controlled data through this path.
  - PlanFilter.value (and any time_range bounds) are user-controlled.
    They are only ever passed as Python values compared against a
    Column object (e.g. `column("x") == value`), which SQLAlchemy
    Core compiles to a bound parameter automatically. They are never
    formatted into a string.
"""

from __future__ import annotations

from typing import Any, Callable, Iterable

from sqlalchemy import ColumnElement, and_, column, func, literal_column, text
from sqlalchemy.sql.elements import ColumnClause
from sqlalchemy.sql.selectable import TableClause

from etl.analytics.metrics.definitions import MetricDefinition
from etl.analytics.context.request_context import TenantScope
from etl.analytics.planner.query_plan import PlanFilter

from .errors import UnsupportedFilterOperatorError

# --------------------------------------------------------------------
# FROM clause
# --------------------------------------------------------------------


def source_table(source_view: str) -> TableClause:
    """
    Build a lightweight FROM target for a fully-qualified view name
    like "analytics.v_sales", without reflecting its schema.

    We deliberately don't use sqlalchemy.Table with a fixed column
    list: the metric registry only tells us about a curated subset of
    columns (supported_dimensions), and the metric expression itself
    references raw underlying columns we never need to name
    individually (e.g. "gross_sales" inside "SUM(gross_sales)"). A
    bare `table()` FromClause is sufficient for a single-table,
    no-join query.
    """
    from sqlalchemy import table as sa_table

    if "." in source_view:
        schema, name = source_view.split(".", 1)
        return sa_table(name, schema=schema)
    return sa_table(source_view)


# --------------------------------------------------------------------
# SELECT list
# --------------------------------------------------------------------


def metric_column(metric: MetricDefinition) -> ColumnElement:
    """
    Render a metric's registry expression (e.g. "SUM(gross_sales)")
    as a labeled SELECT column.

    literal_column is used (not text()) because this needs to behave
    like a column in expression position -- it supports .label() and
    can be referenced the same way a real Column would be.
    metric.expression is trusted registry metadata (see module
    docstring); it is never built from user input.
    """
    return literal_column(metric.expression).label(metric.output_field)


def dimension_column(field: str) -> ColumnElement:
    """A requested GROUP BY / SELECT dimension, labeled by its own name."""
    return column(field).label(field)


# --------------------------------------------------------------------
# Time grain
# --------------------------------------------------------------------

TIME_GRAIN_TO_DATE_TRUNC: dict[str, str] = {
    "daily": "day",
    "weekly": "week",
    "monthly": "month",
    "quarterly": "quarter",
    "yearly": "year",
}


def time_bucket_expr(time_column: str, time_grain: str) -> ColumnElement:
    """
    Build the (unlabeled) DATE_TRUNC expression for a time grain.
    Callers should reuse the SAME expression object for both the
    SELECT list (label it there) and GROUP BY, rather than building
    it twice, so the two are guaranteed to match.
    """
    unit = TIME_GRAIN_TO_DATE_TRUNC[time_grain]
    return func.date_trunc(unit, column(time_column))


# --------------------------------------------------------------------
# WHERE clause -- registry-trusted fixed filters
# --------------------------------------------------------------------


def fixed_filter_clauses(metrics: Iterable[MetricDefinition]) -> list[ColumnElement]:
    """
    Translate each metric's registry-trusted `filters` (raw SQL
    fragments like "direction = 'IN'") into SQLAlchemy text()
    clauses.

    text() is used here -- and ONLY here -- because these fragments
    are developer-authored registry metadata, never user input (see
    module docstring). Deduplicated so a plan combining two metrics
    that share an identical fixed filter doesn't AND the same
    condition in twice.
    """
    seen: dict[str, ColumnElement] = {}
    for metric in metrics:
        for raw_filter in metric.filters:
            if raw_filter not in seen:
                seen[raw_filter] = text(raw_filter) # type: ignore
    return list(seen.values())


# --------------------------------------------------------------------
# WHERE clause -- user-controlled filters
# --------------------------------------------------------------------

FilterOperatorFn = Callable[[ColumnClause, Any], ColumnElement]

FILTER_OPERATORS: dict[str, FilterOperatorFn] = {
    "eq": lambda col, val: col == val,
    "ne": lambda col, val: col != val,
    "gt": lambda col, val: col > val,
    "gte": lambda col, val: col >= val,
    "lt": lambda col, val: col < val,
    "lte": lambda col, val: col <= val,
    "in": lambda col, val: col.in_(val),
    "not_in": lambda col, val: col.notin_(val),
    "like": lambda col, val: col.like(val),
    "ilike": lambda col, val: col.ilike(val),
    "is_null": lambda col, _val: col.is_(None),
    "is_not_null": lambda col, _val: col.isnot(None),
}


def user_filter_clause(plan_filter: PlanFilter) -> ColumnElement:
    """
    Translate one validated PlanFilter into a bound-parameter SQL
    expression. plan_filter.value is a plain Python value compared
    against a Column -- SQLAlchemy binds it automatically; it is
    never interpolated into a string.

    Callers must validate plan_filter.operator against
    FILTER_OPERATORS (and the field against the plan's metrics)
    before calling this -- see sql_builder.py. This function still
    re-checks the operator defensively since it's cheap and this is
    the one place a bad operator could otherwise slip through as a
    raw AttributeError.
    """
    operator_fn = FILTER_OPERATORS.get(plan_filter.operator)
    if operator_fn is None:
        raise UnsupportedFilterOperatorError(
            f"Unsupported filter operator: {plan_filter.operator!r}"
        )
    return operator_fn(column(plan_filter.field), plan_filter.value)


# --------------------------------------------------------------------
# WHERE clause -- time range
# --------------------------------------------------------------------


def time_range_clauses(time_column: str, time_range: Any) -> list[ColumnElement]:
    """
    Translate plan.time_range into bound-parameter comparisons
    against `time_column`.

    QueryPlan.time_range is typed Optional[Any] upstream, so this
    accepts any of:
      - a 2-tuple/list: (start, end)
      - an object exposing .start / .end attributes
      - a mapping exposing "start" / "end" keys
    Either bound may be None/absent to mean "no lower/upper bound".
    `end` is treated as exclusive (bucket-aligned ranges like "this
    month" read most naturally as [start, end)); adjust here if your
    callers construct time_range as inclusive.
    """
    start, end = _extract_time_bounds(time_range)
    col = column(time_column)
    clauses: list[ColumnElement] = []
    if start is not None:
        clauses.append(col >= start)
    if end is not None:
        clauses.append(col < end)
    return clauses


def _extract_time_bounds(time_range: Any) -> tuple[Any, Any]:
    if time_range is None:
        return None, None
    if isinstance(time_range, (tuple, list)) and len(time_range) == 2:
        return time_range[0], time_range[1]
    if hasattr(time_range, "start") and hasattr(time_range, "end"):
        return time_range.start, time_range.end # type: ignore
    if isinstance(time_range, dict):
        return time_range.get("start"), time_range.get("end")
    raise TypeError(
        "Unrecognized time_range shape; expected a (start, end) "
        "tuple, an object with .start/.end, or a {'start','end'} "
        f"mapping, got {type(time_range)!r}."
    )


def combine_where(clauses: Iterable[ColumnElement]) -> ColumnElement | None:
    """AND together every WHERE clause, or None if there are none."""
    clauses = list(clauses)
    if not clauses:
        return None
    if len(clauses) == 1:
        return clauses[0]
    return and_(*clauses)


def tenant_scope_clause(scope: TenantScope) -> ColumnElement:
    """Build the trusted tenant predicate; the tenant ID is bound safely."""
    return column("tenant_id") == scope.tenant_id