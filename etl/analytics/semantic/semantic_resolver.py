"""
Phase 9.3.5 -- Semantic Resolver (orchestrator).

Runs the full resolution pipeline from the roadmap:

    AnalyticalQueryRequest
        |
        +-- Resolve metric (+ additional_metrics)
        |
        +-- Resolve & validate dimensions   (Metric x Dimension compat.)
        |
        +-- Resolve filter names & values    (Metric x Filter compat.)
        |
        v
    ResolvedAnalyticalQuery

Design rule from the roadmap, upheld here: Semantic Resolution must
not generate SQL. This module doesn't touch etl.analytics.query at
all -- it only produces a ResolvedAnalyticalQuery, which downstream
code eventually turns into an AnalyticalQueryRequest
(.to_analytical_query_request()) and, once time-resolved, a
QueryRequest (Phase 8).

Doesn't talk to a database directly either: entity lookups go through
an injected EntityLookupFn (see filter_resolver.py), the same
dependency-injection pattern Phase 9.2 used for the LLM call.
"""

from __future__ import annotations

from typing import Optional

from etl.analytics.schemas import AnalyticalQueryRequest
from etl.analytics.metrics.registry import get_metric
from etl.analytics.semantic.dimension_resolver import resolve_dimension
from etl.analytics.semantic.filter_resolver import EntityLookupFn, resolve_filter
from etl.analytics.semantic.metric_resolver import resolve_metric
from etl.analytics.semantic.models import (
    ResolutionResult,
    ResolvedAnalyticalQuery,
    ResolvedFilter,
    SemanticResolutionError,
)


def _allowed_dimensions(metric_names: tuple[str, ...]) -> frozenset[str]:
    """Union of supported_dimensions across all requested (already
    resolved) metrics -- mirrors etl.analytics.query.validator's own
    _allowed_dimensions, reusing the same registry data rather than
    duplicating a second copy of it."""
    dims: set[str] = set()
    for name in metric_names:
        dims.update(get_metric(name).supported_dimensions)
    return frozenset(dims)


class SemanticResolver:
    """
    Turns a Phase 9.2 AnalyticalQueryRequest (raw user language) into
    a Phase 9.3 ResolvedAnalyticalQuery (canonical business/analytics
    concepts).

        resolver = SemanticResolver()  # or SemanticResolver(entity_lookup=my_lookup)
        resolved = resolver.resolve(request)

    Raises:
        SemanticResolutionError: If any metric/dimension/filter piece
            couldn't be cleanly resolved. Carries EVERY failing
            ResolutionResult (`error.issues`), gathered in one pass,
            rather than stopping at the first problem -- except that
            metric resolution is checked first and short-circuits on
            its own failure, since dimension/filter compatibility
            can't even be evaluated without knowing which metric(s)
            were requested.
    """

    def __init__(self, entity_lookup: Optional[EntityLookupFn] = None) -> None:
        self._entity_lookup = entity_lookup

    def resolve(self, request: AnalyticalQueryRequest) -> ResolvedAnalyticalQuery:
        metric_result = resolve_metric(request.metric, field_name="metric")
        additional_results = [
            resolve_metric(name, field_name=f"additional_metrics[{i}]")
            for i, name in enumerate(request.additional_metrics)
        ]

        metric_issues = tuple(
            r for r in (metric_result, *additional_results) if not r.is_resolved
        )
        if metric_issues:
            raise SemanticResolutionError(metric_issues)

        resolved_metric: str = metric_result.resolved_value
        resolved_additional: tuple[str, ...] = tuple(r.resolved_value for r in additional_results)
        allowed_dimensions = _allowed_dimensions((resolved_metric,) + resolved_additional)

        dimension_results = [
            resolve_dimension(
                dim, allowed_dimensions=allowed_dimensions, field_name=f"dimensions[{i}]"
            )
            for i, dim in enumerate(request.dimensions)
        ]

        filter_results: list[ResolutionResult] = []
        resolved_filters: list[ResolvedFilter] = []
        for f in request.filters:
            result, resolved_filter = resolve_filter(
                f, allowed_dimensions=allowed_dimensions, entity_lookup=self._entity_lookup
            )
            filter_results.append(result)
            if resolved_filter is not None:
                resolved_filters.append(resolved_filter)

        issues = tuple(r for r in (*dimension_results, *filter_results) if not r.is_resolved)
        if issues:
            raise SemanticResolutionError(issues)

        return ResolvedAnalyticalQuery(
            metric=resolved_metric,
            additional_metrics=resolved_additional,
            dimensions=tuple(r.resolved_value for r in dimension_results),
            filters=tuple(resolved_filters),
            time_grain=request.time_grain,
            time_range=request.time_range,
            limit=request.limit,
            sort_by=request.sort_by,
            sort_order=request.sort_order,
            comparison=request.comparison,
            raw_question=request.raw_question,
        )
