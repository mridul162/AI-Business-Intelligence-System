"""
Analytical Query Contract (Phase 9.1) — public surface.

    from ai.analytics.schemas import (
        AnalyticalQueryRequest,
        FilterCondition,
        ComparisonSpec,
        TimeRange,
        NotResolvedError,
        KNOWN_TIME_GRAINS,
        KNOWN_FILTER_OPERATORS,
        KNOWN_COMPARISON_MODES,
    )
    from ai.analytics.schemas.time_range import KNOWN_PRESETS

This is the contract the NL/LLM layer (Phase 9.2) produces. It is
converted to `etl.analytics.query.QueryRequest` — the existing,
already-validated Phase 8 contract — once every field is resolved:

    AnalyticalQueryRequest (this package)
            │
            │  Phase 9.4 time resolver fills in TimeRange.start/end
            ▼
    request.to_query_request()
            │
            ▼
    etl.analytics.query.build_query(...)   # Phase 8, unchanged
"""

from etl.analytics.schemas.analytical_query import (
    KNOWN_COMPARISON_MODES,
    KNOWN_FILTER_OPERATORS,
    KNOWN_TIME_GRAINS,
    AnalyticalQueryRequest,
    ComparisonSpec,
    FilterCondition,
    NotResolvedError,
)
from etl.analytics.schemas.time_range import KNOWN_PRESETS, TimeRange

__all__ = [
    "AnalyticalQueryRequest",
    "FilterCondition",
    "ComparisonSpec",
    "TimeRange",
    "NotResolvedError",
    "KNOWN_TIME_GRAINS",
    "KNOWN_FILTER_OPERATORS",
    "KNOWN_COMPARISON_MODES",
    "KNOWN_PRESETS",
]
