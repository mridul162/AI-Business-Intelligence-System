"""
Semantic Resolution Layer (Phase 9.3) -- public surface.

    from etl.analytics.semantic import (
        SemanticResolver,
        SemanticResolutionError,
        ResolutionStatus,
        ResolutionResult,
        ResolvedAnalyticalQuery,
        ResolvedFilter,
        EntityMatch,
        EntityLookupFn,
        StaticEntityDirectory,
    )

    resolver = SemanticResolver()  # no entity directory: entity-name
                                    # filters pass through as names,
                                    # not IDs -- see filter_resolver.py
    resolved = resolver.resolve(analytical_query_request)
    # resolved is a ResolvedAnalyticalQuery: canonical metric name(s),
    # canonical dimension names, canonical filter dimensions/values.
    # time_range/time_grain are carried through untouched -- still
    # Phase 9.4's job.
"""

from etl.analytics.semantic.filter_resolver import (
    EntityLookupFn,
    EntityMatch,
    StaticEntityDirectory,
    resolve_filter,
)
from etl.analytics.semantic.dimension_resolver import DIMENSION_ALIASES, resolve_dimension
from etl.analytics.semantic.metric_resolver import resolve_metric
from etl.analytics.semantic.models import (
    ResolutionResult,
    ResolutionStatus,
    ResolvedAnalyticalQuery,
    ResolvedFilter,
    SemanticResolutionError,
)
from etl.analytics.semantic.semantic_resolver import SemanticResolver

__all__ = [
    "SemanticResolver",
    "SemanticResolutionError",
    "ResolutionStatus",
    "ResolutionResult",
    "ResolvedAnalyticalQuery",
    "ResolvedFilter",
    "EntityMatch",
    "EntityLookupFn",
    "StaticEntityDirectory",
    "DIMENSION_ALIASES",
    "resolve_metric",
    "resolve_dimension",
    "resolve_filter",
]
