"""
Analytical Query Contract and Query Builder (Phase 8.2).

Public surface:

    from etl.analytics.query import (
        QueryRequest,
        QueryFilter,
        OrderBy,
        FilterOperator,
        CompiledQuery,
        build_query,
        ValidationError,
        BuildError,
    )

    request = QueryRequest(
        metrics=("gross_sales",),
        dimensions=("product_category",),
        time_grain="monthly",
        date_from=date(2026, 1, 1),
        date_to=date(2026, 12, 31),
    )
    compiled = build_query(request)
    # compiled.sql    -> parameterized SQL text
    # compiled.params -> dict of bound values

The LLM/agent layer only ever produces a QueryRequest. It never sees
or writes SQL; build_query() is the only bridge to the warehouse, and
validate_query() (called internally by build_query) is the safety
boundary that rejects anything unsafe or malformed before SQL is
generated.
"""

from etl.analytics.query.models import (
    CompiledQuery,
    FilterOperator,
    OrderBy,
    QueryFilter,
    QueryRequest,
)
from etl.analytics.query.validator import ValidationError, validate_query
from etl.analytics.query.builder import BuildError, build_query

__all__ = [
    "QueryRequest",
    "QueryFilter",
    "OrderBy",
    "FilterOperator",
    "CompiledQuery",
    "build_query",
    "validate_query",
    "ValidationError",
    "BuildError",
]