"""
Phase 9.3.1 -- Semantic Resolution models.

This is the contract every resolver in this layer (metric_resolver,
dimension_resolver, filter_resolver) returns, and the contract the
whole layer's orchestrator (semantic_resolver.SemanticResolver)
converts an ai.analytics.schemas.AnalyticalQueryRequest into.

    AnalyticalQueryRequest              (Phase 9.1/9.2 -- raw user language)
            |
            v  SemanticResolver.resolve()
            |
    ResolvedAnalyticalQuery             (Phase 9.3 -- canonical business/analytics concepts)

Nothing here talks to a database, the metric registry, or an LLM --
same discipline as ai.analytics.schemas: pure shape, no execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from etl.analytics.schemas import AnalyticalQueryRequest, ComparisonSpec, FilterCondition, TimeRange


class ResolutionStatus(str, Enum):
    """The outcome of trying to resolve one piece of raw user
    language to something canonical."""

    RESOLVED = "resolved"
    NOT_FOUND = "not_found"
    AMBIGUOUS = "ambiguous"
    INVALID = "invalid"


@dataclass(frozen=True)
class ResolutionResult:
    """
    The outcome of resolving one piece of raw user language (a metric
    name, a dimension alias, a filter value, ...) to something
    canonical.

    `resolved_value` is deliberately typed `Any` rather than `str`:
    for a metric or dimension it's a plain canonical name string; for
    a filter (see filter_resolver.resolve_filter) the canonical value
    is a richer `ResolvedFilter`. Either way it's only populated when
    `status is ResolutionStatus.RESOLVED`.

    `field_name` identifies WHAT was being resolved (e.g. "metric",
    "dimensions[0]", "filter:location") so a caller presenting
    several issues at once (see SemanticResolutionError) can tell them
    apart without re-deriving that from `original_value`.
    """

    status: ResolutionStatus
    original_value: str
    field_name: str
    resolved_value: Any = None
    candidates: tuple[str, ...] = field(default_factory=tuple)
    message: Optional[str] = None

    @property
    def is_resolved(self) -> bool:
        return self.status is ResolutionStatus.RESOLVED

    @classmethod
    def resolved(cls, field_name: str, original_value: str, resolved_value: Any) -> "ResolutionResult":
        return cls(
            status=ResolutionStatus.RESOLVED,
            original_value=original_value,
            field_name=field_name,
            resolved_value=resolved_value,
        )

    @classmethod
    def not_found(
        cls, field_name: str, original_value: str, message: Optional[str] = None
    ) -> "ResolutionResult":
        return cls(
            status=ResolutionStatus.NOT_FOUND,
            original_value=original_value,
            field_name=field_name,
            message=message or f"Could not resolve {field_name} value {original_value!r}.",
        )

    @classmethod
    def ambiguous(
        cls,
        field_name: str,
        original_value: str,
        candidates: tuple[str, ...],
        message: Optional[str] = None,
    ) -> "ResolutionResult":
        return cls(
            status=ResolutionStatus.AMBIGUOUS,
            original_value=original_value,
            field_name=field_name,
            candidates=tuple(candidates),
            message=message or (
                f"{field_name} value {original_value!r} is ambiguous. "
                f"Candidates: {', '.join(candidates)}"
            ),
        )

    @classmethod
    def invalid(cls, field_name: str, original_value: str, message: str) -> "ResolutionResult":
        return cls(
            status=ResolutionStatus.INVALID,
            original_value=original_value,
            field_name=field_name,
            message=message,
        )


class SemanticResolutionError(Exception):
    """
    Raised by SemanticResolver.resolve() when one or more parts of a
    request couldn't be cleanly resolved to canonical business
    concepts.

    Carries EVERY failing ResolutionResult (`.issues`), not just the
    first -- so a caller (e.g. a chat UI) can show the user all the
    ambiguity/not-found problems in one turn ("Which 'earnings' did
    you mean: gross_sales, net_sales, or gross_business_margin? Also,
    I couldn't find a location called 'Mirpurr'.") instead of a
    frustrating one-error-at-a-time loop.
    """

    def __init__(self, issues: tuple[ResolutionResult, ...]) -> None:
        self.issues = issues
        summary = "; ".join(f"{i.field_name}: {i.message}" for i in issues)
        super().__init__(f"Semantic resolution failed ({len(issues)} issue(s)): {summary}")


@dataclass(frozen=True)
class ResolvedFilter:
    """
    One filter condition after semantic resolution: canonical
    dimension name and canonical value(s) (e.g. an entity ID instead
    of a typed name), with the original raw dimension/value kept
    alongside for traceability, debugging, and Phase 9.6's response
    grounding (so a generated answer can say "for Mirpur Branch"
    instead of just "for LOC_001").
    """

    dimension: str
    operator: str
    value: Any
    original_dimension: str
    original_value: Any


@dataclass(frozen=True)
class ResolvedAnalyticalQuery:
    """
    The Phase 9.3 output: an AnalyticalQueryRequest whose `metric`,
    `additional_metrics`, `dimensions`, and `filters` are now
    canonical business/analytics concepts (real registry metric
    names, real column names, real entity IDs where applicable)
    instead of raw user language.

    time_grain / time_range / limit / sort_by / sort_order /
    comparison are carried through UNCHANGED -- this layer resolves
    *identity* only (which metric, which dimension, which entity),
    never time and never SQL. An unresolved `time_range` (see
    ai.analytics.schemas.TimeRange) is still Phase 9.4's job.
    """

    metric: str
    additional_metrics: tuple[str, ...] = field(default_factory=tuple)
    dimensions: tuple[str, ...] = field(default_factory=tuple)
    filters: tuple[ResolvedFilter, ...] = field(default_factory=tuple)
    time_grain: Optional[str] = None
    time_range: Optional[TimeRange] = None
    limit: Optional[int] = None
    sort_by: Optional[str] = None
    sort_order: str = "desc"
    comparison: Optional[ComparisonSpec] = None
    raw_question: Optional[str] = None

    @property
    def all_metrics(self) -> tuple[str, ...]:
        return (self.metric,) + tuple(self.additional_metrics)

    def to_analytical_query_request(self) -> AnalyticalQueryRequest:
        """
        Bridge back to the Phase 9.1 contract, now with canonical
        names/ids, so it can continue unchanged through Phase 9.4
        (time resolution) and AnalyticalQueryRequest.to_query_request()
        (Phase 8) -- the same "one to_X() bridge per phase boundary"
        pattern AnalyticalQueryRequest itself uses.
        """
        return AnalyticalQueryRequest(
            metric=self.metric,
            additional_metrics=self.additional_metrics,
            dimensions=self.dimensions,
            filters=tuple(
                FilterCondition(dimension=f.dimension, operator=f.operator, value=f.value)
                for f in self.filters
            ),
            time_grain=self.time_grain,
            time_range=self.time_range,
            limit=self.limit,
            sort_by=self.sort_by,
            sort_order=self.sort_order,
            comparison=self.comparison,
            raw_question=self.raw_question,
        )
