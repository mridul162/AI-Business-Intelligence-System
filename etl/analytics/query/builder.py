"""
Analytical Query Builder.

Turns a validated QueryRequest into a single parameterized SQL
statement against one analytics.* view.

Design notes
------------
Multiple metrics in one request may legitimately carry *different*
built-in filters (e.g. `cash_in` filters `direction = 'IN'` while
`cash_out` filters `direction = 'OUT'`, both against
analytics.v_cash_transactions). A plain WHERE clause can't express
that — WHERE applies to every metric in the query equally. Instead,
each metric's own filters are pushed *inside* its aggregate as a
CASE WHEN, so `cash_in` and `cash_out` can be selected side by side
in one grouped query without one clobbering the other:

    SUM(CASE WHEN direction = 'IN'  THEN amount ELSE NULL END) AS cash_in,
    SUM(CASE WHEN direction = 'OUT' THEN amount ELSE NULL END) AS cash_out

Request-level filters (`QueryRequest.filters`, `date_from`/`date_to`)
are different: they're supplied by the caller to scope the *whole*
query, so those go in a real WHERE clause instead.

Only trusted, code-defined strings (view names, column names,
registry-authored filter fragments) are ever interpolated directly
into SQL text. Every value that came from the caller — filter values,
date bounds — is bound as a parameter and never touches the SQL
string directly.
"""

from __future__ import annotations

import re

from etl.analytics.metrics.definitions import MetricDefinition
from etl.analytics.query.models import (
    LIST_OPERATORS,
    NULLARY_OPERATORS,
    CompiledQuery,
    FilterOperator,
    QueryFilter,
    QueryRequest,
)
from etl.analytics.query.time_grains import (
    PERIOD_ALIAS,
    date_trunc_expression,
    primary_date_column,
)
from etl.analytics.query.validator import ValidatedQuery, validate_query

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# aggregation -> regex that strips the wrapper off MetricDefinition.expression
# to recover the bare inner expression, so it can be re-wrapped in a
# CASE WHEN for conditional aggregation.
_AGG_UNWRAP_PATTERNS: dict[str, re.Pattern[str]] = {
    "sum": re.compile(r"^SUM\((.+)\)$", re.IGNORECASE),
    "count": re.compile(r"^COUNT\((.+)\)$", re.IGNORECASE),
    "count_distinct": re.compile(r"^COUNT\(DISTINCT\s+(.+)\)$", re.IGNORECASE),
    "average": re.compile(r"^AVG\((.+)\)$", re.IGNORECASE),
}

_AGG_REWRAP: dict[str, str] = {
    "sum": "SUM({inner})",
    "count": "COUNT({inner})",
    "count_distinct": "COUNT(DISTINCT {inner})",
    "average": "AVG({inner})",
}


class BuildError(Exception):
    """Raised when a validated request still can't be compiled to SQL
    (e.g. a metric's `expression` doesn't match its declared
    `aggregation`, or a ratio metric with built-in `filters` is
    requested — unsupported in this phase).

    KNOWN LIMITATION: a `ratio` metric with *no* built-in `filters`
    is not rejected — it bypasses the CASE WHEN rewrap path entirely
    and its `expression` is spliced in as-is, since there's nothing
    to unwrap. No ratio metrics are registered yet (Phase 8.1's
    registry only uses sum/count/count_distinct), so this is latent
    rather than active. Phase 8.3 should add real numerator/
    denominator fields to MetricDefinition and a NULLIF-based
    division path (honoring `null_if_denominator_zero`) instead of
    relying on this pass-through."""


class _ParamAllocator:
    """Generates unique, collision-free named placeholders and
    accumulates their bound values."""

    def __init__(self) -> None:
        self._params: dict[str, object] = {}
        self._counter = 0

    def add(self, value: object) -> str:
        self._counter += 1
        name = f"p{self._counter}"
        self._params[name] = value
        return name

    @property
    def params(self) -> dict[str, object]:
        return dict(self._params)


def _require_identifier(name: str, what: str) -> str:
    if not _IDENTIFIER_RE.match(name):
        raise BuildError(f"Unsafe {what} identifier: {name!r}")
    return name


def _inner_expression(metric: MetricDefinition) -> str:
    """Strip the aggregation wrapper off metric.expression, e.g.
    'SUM(gross_sales)' -> 'gross_sales'."""

    pattern = _AGG_UNWRAP_PATTERNS.get(metric.aggregation)
    if pattern is None:
        raise BuildError(
            f"Metric '{metric.name}' uses aggregation "
            f"'{metric.aggregation}', which this builder can't yet "
            f"compile (ratio metrics need numerator/denominator "
            f"support — planned for Phase 8.3)."
        )

    match = pattern.match(metric.expression.strip())
    if not match:
        raise BuildError(
            f"Metric '{metric.name}' declares aggregation="
            f"'{metric.aggregation}' but its expression "
            f"{metric.expression!r} doesn't match the expected "
            f"'{metric.aggregation.upper()}(...)' shape. Fix the "
            f"registry entry."
        )
    return match.group(1).strip()


def _metric_select_expression(metric: MetricDefinition) -> str:
    """Build the `<agg expr> AS <output_field>` fragment for one
    metric, pushing the metric's own built-in filters (if any) inside
    the aggregate as a CASE WHEN so multiple differently-filtered
    metrics on the same view can be selected together."""

    output_field = _require_identifier(metric.output_field, "metric output_field")

    if metric.filters:
        # Metric-authored filter fragments are trusted (they come
        # from registry.py, not from the caller), so they're safe to
        # splice directly.
        condition = " AND ".join(metric.filters)
        inner = _inner_expression(metric)
        rewrap = _AGG_REWRAP[metric.aggregation]
        agg_expr = rewrap.format(inner=f"CASE WHEN {condition} THEN {inner} ELSE NULL END")
    else:
        agg_expr = metric.expression

    if metric.zero_if_no_data:
        agg_expr = f"COALESCE({agg_expr}, 0)"

    return f"{agg_expr} AS {output_field}"


def _render_filter(filt: QueryFilter, params: _ParamAllocator) -> str:
    col = _require_identifier(filt.dimension, "filter dimension")

    if filt.operator in NULLARY_OPERATORS:
        return f"{col} IS NULL" if filt.operator is FilterOperator.IS_NULL else f"{col} IS NOT NULL"

    if filt.operator in LIST_OPERATORS:
        p = params.add(list(filt.value))
        if filt.operator is FilterOperator.IN:
            return f"{col} = ANY(%({p})s)"
        return f"NOT ({col} = ANY(%({p})s))"

    if filt.operator is FilterOperator.BETWEEN:
        lo, hi = filt.value
        p_lo = params.add(lo)
        p_hi = params.add(hi)
        return f"{col} BETWEEN %({p_lo})s AND %({p_hi})s"

    op_sql = {
        FilterOperator.EQ: "=",
        FilterOperator.NE: "!=",
        FilterOperator.GT: ">",
        FilterOperator.GTE: ">=",
        FilterOperator.LT: "<",
        FilterOperator.LTE: "<=",
        FilterOperator.LIKE: "LIKE",
    }[filt.operator]

    p = params.add(filt.value)
    return f"{col} {op_sql} %({p})s"


def _build_where_clause(
    request: QueryRequest, source_view: str, params: _ParamAllocator
) -> str:
    conditions: list[str] = []

    for filt in request.filters:
        conditions.append(_render_filter(filt, params))

    if request.date_from is not None or request.date_to is not None:
        date_col = primary_date_column(source_view)
        if request.date_from is not None:
            p = params.add(request.date_from)
            conditions.append(f"{date_col} >= %({p})s")
        if request.date_to is not None:
            p = params.add(request.date_to)
            conditions.append(f"{date_col} <= %({p})s")

    if not conditions:
        return ""
    return "WHERE " + " AND ".join(conditions)


def build_query(request: QueryRequest) -> CompiledQuery:
    """Validate and compile a QueryRequest into parameterized SQL.

    Raises:
        etl.analytics.query.validator.ValidationError: If the request is
            unsafe or malformed.
        BuildError: If the request is valid but can't be compiled
            (e.g. a requested metric is a not-yet-supported ratio).
    """

    validated: ValidatedQuery = validate_query(request)
    metrics = validated.metrics
    source_view = validated.source_view

    for dim in request.dimensions:
        _require_identifier(dim, "dimension")

    params = _ParamAllocator()

    select_parts: list[str] = list(request.dimensions)

    if request.time_grain is not None:
        bucket_expr = date_trunc_expression(source_view, request.time_grain)
        select_parts.append(f"{bucket_expr} AS {PERIOD_ALIAS}")

    for metric in metrics:
        select_parts.append(_metric_select_expression(metric))

    where_clause = _build_where_clause(request, source_view, params)

    group_by_parts: list[str] = list(request.dimensions)
    if request.time_grain is not None:
        group_by_parts.append(PERIOD_ALIAS)
    group_by_clause = (
        f"GROUP BY {', '.join(group_by_parts)}" if group_by_parts else ""
    )

    order_by_clause = ""
    if request.order_by:
        order_parts = [
            f"{_require_identifier(o.field, 'order_by field')} "
            f"{'DESC' if o.direction == 'desc' else 'ASC'}"
            for o in request.order_by
        ]
        order_by_clause = "ORDER BY " + ", ".join(order_parts)

    limit_clause = ""
    if request.limit is not None:
        p = params.add(request.limit)
        limit_clause = f"LIMIT %({p})s"

    sql = "\n".join(
        part
        for part in (
            f"SELECT {', '.join(select_parts)}",
            f"FROM {source_view}",
            where_clause,
            group_by_clause,
            order_by_clause,
            limit_clause,
        )
        if part
    )

    output_columns = tuple(request.dimensions) + (
        (PERIOD_ALIAS,) if request.time_grain is not None else ()
    ) + tuple(m.output_field for m in metrics)

    return CompiledQuery(sql=sql, params=params.params, output_columns=output_columns)