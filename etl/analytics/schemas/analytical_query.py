"""
Analytical Query Contract (Phase 9.1).

This is the structured representation an NL/LLM layer is allowed to
produce. It is deliberately *not* the same type as
`etl.analytics.query.QueryRequest`:

  - QueryRequest is Phase 8's contract: every field is already
    validated-shape and ready for SQL compilation (resolved dates,
    real FilterOperator values, identifiers that must exist).

  - AnalyticalQueryRequest is Phase 9's contract: fields may still be
    *unresolved* (a time range preset instead of dates, a metric
    alias instead of a confirmed registry name). It's the output of
    "the LLM decided what the user means" and the input to the
    deterministic pipeline (metric resolution, time resolution,
    validation) that turns it into a QueryRequest.

Nothing in this module talks to a database, a registry, or an LLM.
It only defines shape and rejects structurally nonsensical input
(e.g. an unknown operator string, a negative limit). Whether a
`metric` name or `dimension` actually exists is Phase 9.3's job, not
this one — same separation of concerns as Phase 8's
validator.py-vs-models.py split.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from etl.analytics.query.models import FilterOperator, OrderBy, QueryFilter, QueryRequest

from etl.analytics.schemas.time_range import TimeRange

# Grains the downstream query layer understands (etl.analytics.metrics
# .definitions.TimeGrain). Duplicated here as plain strings rather than
# imported as a Literal so this module doesn't need typing.Literal
# gymnastics; the values must stay in sync with that Literal.
KNOWN_TIME_GRAINS = frozenset({"daily", "weekly", "monthly", "quarterly", "yearly"})

# Operators an LLM is allowed to emit on a FilterCondition. Mirrors
# etl.analytics.query.models.FilterOperator's values.
KNOWN_FILTER_OPERATORS = frozenset(op.value for op in FilterOperator)

_SORT_ORDERS = frozenset({"asc", "desc"})

# Comparison modes reserved by the contract now so AnalyticalQueryRequest's
# shape doesn't need to change when comparison support is actually built.
KNOWN_COMPARISON_MODES = frozenset({"previous_period", "same_period_last_year"})


class NotResolvedError(Exception):
    """Raised by AnalyticalQueryRequest.to_query_request() when the
    request still has unresolved parts (an unresolved TimeRange, or a
    comparison) that must go through the Phase 9.4 time resolver /
    Phase 9.5 query planner before they can become a QueryRequest."""


@dataclass(frozen=True)
class FilterCondition:
    """
    One filter the NL layer believes applies to the query.

    `dimension` and `value` are taken at face value here — e.g. a
    caller may write `FilterCondition("customer_name", "eq", "Karim")`
    even though the underlying column is `customer_id`. Resolving a
    human-readable value/dimension to what the registry actually
    supports is Phase 9.3's (dimension_resolver.py) job, not this
    contract's.
    """

    dimension: str
    operator: str = "eq"
    value: Any = None

    def __post_init__(self) -> None:
        if not isinstance(self.dimension, str) or not self.dimension:
            raise ValueError("FilterCondition.dimension must be a non-empty string.")
        if self.operator not in KNOWN_FILTER_OPERATORS:
            raise ValueError(
                f"Unknown filter operator {self.operator!r}. Must be one "
                f"of: {sorted(KNOWN_FILTER_OPERATORS)}"
            )

    def to_query_filter(self) -> QueryFilter:
        """Convert to the Phase 8 QueryFilter. Assumes `dimension` has
        already been resolved to a real column name (Phase 9.3) — this
        does not check that here, only that the operator is one of the
        values FilterOperator recognizes."""
        return QueryFilter(
            dimension=self.dimension,
            operator=FilterOperator(self.operator),
            value=self.value,
        )


@dataclass(frozen=True)
class ComparisonSpec:
    """
    Placeholder for period-over-period comparison requests, e.g.
    "sales this month vs last month". Reserved on the contract now so
    later phases don't need to change AnalyticalQueryRequest's shape.

    Not resolved or executed anywhere yet — a request carrying a
    ComparisonSpec cannot currently be converted to a QueryRequest
    (see AnalyticalQueryRequest.to_query_request), since the Phase 8
    query layer has no comparison concept.
    """

    mode: str

    def __post_init__(self) -> None:
        if self.mode not in KNOWN_COMPARISON_MODES:
            raise ValueError(
                f"Unknown comparison mode {self.mode!r}. Must be one of: "
                f"{sorted(KNOWN_COMPARISON_MODES)}"
            )


@dataclass(frozen=True)
class AnalyticalQueryRequest:
    """
    A structured analytical request as produced by the NL/LLM layer.

    `metric` is the primary metric the user asked about (an alias or
    a real registry name — not yet confirmed). `additional_metrics`
    covers the same-source-view multi-metric case the existing query
    layer already supports (e.g. "cash in and cash out this month").

    This type intentionally accepts more than the query layer can
    execute today (unresolved time ranges, comparisons) — call
    `is_ready_for_query_layer()` to check, or `to_query_request()` to
    convert and get a clear error if something still needs resolving.
    """

    metric: str
    additional_metrics: tuple[str, ...] = field(default_factory=tuple)
    dimensions: tuple[str, ...] = field(default_factory=tuple)
    filters: tuple[FilterCondition, ...] = field(default_factory=tuple)
    time_grain: str | None = None
    time_range: TimeRange | None = None
    limit: int | None = None
    sort_by: str | None = None
    sort_order: str = "desc"
    comparison: ComparisonSpec | None = None
    # The original user question, carried through the pipeline so the
    # Phase 9.6 response generator can ground its answer in both the
    # question and the resolved interpretation (per the roadmap's
    # "this helps prevent hallucinated interpretations").
    raw_question: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.metric, str) or not self.metric:
            raise ValueError("AnalyticalQueryRequest.metric must be a non-empty string.")
        if self.sort_order not in _SORT_ORDERS:
            raise ValueError(
                f"sort_order must be 'asc' or 'desc', got {self.sort_order!r}."
            )
        if self.time_grain is not None and self.time_grain not in KNOWN_TIME_GRAINS:
            raise ValueError(
                f"Unknown time_grain {self.time_grain!r}. Must be one of: "
                f"{sorted(KNOWN_TIME_GRAINS)}"
            )
        if self.limit is not None and (
            isinstance(self.limit, bool) or not isinstance(self.limit, int) or self.limit <= 0
        ):
            raise ValueError("limit must be a positive integer.")

    @property
    def all_metrics(self) -> tuple[str, ...]:
        """All metrics this request touches, primary first."""
        return (self.metric,) + tuple(self.additional_metrics)

    def is_ready_for_query_layer(self) -> bool:
        """True once every field is in a shape the existing
        etl.analytics.query layer can consume — i.e. no unresolved
        time range and no comparison. This checks *shape* only: it
        does NOT confirm `metric`/`dimensions`/filter values actually
        exist in the metric registry. That check happens when
        `to_query_request()`'s result is passed to `build_query()`,
        which runs Phase 8's validator."""
        if self.time_range is not None and not self.time_range.is_resolved:
            return False
        if self.comparison is not None:
            return False
        return True

    def to_query_request(self) -> QueryRequest:
        """
        Convert to the Phase 8 QueryRequest the existing query layer
        executes.

        Raises:
            NotResolvedError: If this request still has an unresolved
                TimeRange or a ComparisonSpec attached. Run it through
                the Phase 9.4 time resolver (and, once built, the
                comparison planner) first.

        Note this does NOT validate that `metric`, `dimensions`, or
        filter dimensions are real registry entries — that happens
        when the returned QueryRequest reaches `build_query()`
        (Phase 8's validate_query). Catch
        `etl.analytics.query.ValidationError` there for that class of
        error.
        """
        if self.time_range is not None and not self.time_range.is_resolved:
            raise NotResolvedError(
                "TimeRange is unresolved (preset="
                f"{self.time_range.preset!r}, label={self.time_range.label!r}). "
                "Run it through the time resolver before calling "
                "to_query_request()."
            )
        if self.comparison is not None:
            raise NotResolvedError(
                f"Comparison mode {self.comparison.mode!r} is set, but the "
                "query layer has no comparison support yet. Split this "
                "into separate requests (one per period) instead."
            )

        order_by: tuple[OrderBy, ...] = ()
        if self.sort_by is not None:
            order_by = (OrderBy(field=self.sort_by, direction=self.sort_order),)

        date_from = self.time_range.start if self.time_range is not None else None
        date_to = self.time_range.end if self.time_range is not None else None

        return QueryRequest(
            metrics=self.all_metrics,
            dimensions=self.dimensions,
            time_grain=self.time_grain, #type: ignore[assignment]
            filters=tuple(f.to_query_filter() for f in self.filters),
            date_from=date_from,
            date_to=date_to,
            order_by=order_by,
            limit=self.limit,
        )
