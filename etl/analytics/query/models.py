"""
Analytical Query Contract.

This module defines the *shape* of a query request that the LLM/agent
layer is allowed to produce, and the shape of the compiled SQL that
comes out of the builder. Nothing in this file talks to a database or
constructs SQL strings — it is pure data.

The contract is intentionally small and closed: an agent can only
express a query in terms of metric names (resolved via the metric
registry), dimension names, a time grain, filters, an optional date
range, ordering, and a limit. It can never supply raw SQL.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from datetime import date
from typing import Any, Union

from etl.analytics.metrics.definitions import TimeGrain


class FilterOperator(str, Enum):
    """Supported comparison operators for QueryFilter.value."""

    EQ = "eq"
    NE = "ne"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    IN = "in"
    NOT_IN = "not_in"
    LIKE = "like"
    IS_NULL = "is_null"
    IS_NOT_NULL = "is_not_null"
    BETWEEN = "between"


# Operators that take no value at all.
NULLARY_OPERATORS = (FilterOperator.IS_NULL, FilterOperator.IS_NOT_NULL)

# Operators that expect a list/tuple of values.
LIST_OPERATORS = (FilterOperator.IN, FilterOperator.NOT_IN)


@dataclass(frozen=True)
class QueryFilter:
    """
    One WHERE-clause condition on a dimension column.

    `dimension` must be a column name — never a raw SQL expression.
    The validator checks it against the set of dimensions supported
    by the requested metrics before the builder ever touches it.
    """

    dimension: str
    operator: FilterOperator
    value: Any = None


@dataclass(frozen=True)
class OrderBy:
    """One ORDER BY entry. `field` must be a dimension, the time
    bucket alias ('period'), or a requested metric's output_field."""

    field: str
    direction: str = "asc"  # "asc" | "desc"


@dataclass(frozen=True)
class QueryRequest:
    """
    A declarative request for one analytical query.

    All metrics in a single request must share the same
    `source_view` (enforced by the validator) — this builder does
    not join across analytics views. Requesting metrics from
    different views requires issuing separate QueryRequests.
    """

    metrics: tuple[str, ...]
    dimensions: tuple[str, ...] = field(default_factory=tuple)
    time_grain: Union[TimeGrain, None] = None
    filters: tuple[QueryFilter, ...] = field(default_factory=tuple)
    date_from: Union[date, None] = None
    date_to: Union[date, None] = None
    order_by: tuple[OrderBy, ...] = field(default_factory=tuple)
    limit: Union[int, None] = None


@dataclass(frozen=True)
class CompiledQuery:
    """
    The output of the query builder: a parameterized SQL statement.

    `sql` uses psycopg2-style named placeholders (`%(name)s`). No
    value from the request is ever interpolated directly into `sql`
    — values only ever appear in `params`. Identifiers (view/column
    names) are validated against known-safe allowlists before being
    interpolated, since SQL does not allow parameterizing identifiers.
    """

    sql: str
    params: dict[str, Any]
    output_columns: tuple[str, ...]