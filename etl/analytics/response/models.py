"""
The public analytical response contract.

Everything downstream of the pipeline (an API route, a dashboard, an
LLM explaining results, a chat UI) should only ever need to know about
AnalyticalResponse. It should never need to understand ParsedQuery,
QueryRequest, CompiledQuery, or QueryExecutionResult — those are
internal pipeline types.

Kept as plain dataclasses (not Pydantic) to match the style already
used by QueryRequest, CompiledQuery, QueryExecutionResult, and
AnalyticalQueryResponse elsewhere in this codebase. Swap to Pydantic
here if your project actually standardizes on it elsewhere — nothing
else in this layer depends on the choice.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Union


class AnalyticalResponseStatus(str, Enum):
    """Explicit, closed set of response statuses.

    Deliberately small. Resist the urge to add more without a strong
    reason — the whole point is to prevent statuses like "successful",
    "no_data", "empty_result" from creeping in as synonyms for these
    three.
    """

    SUCCESS = "success"
    EMPTY = "empty"
    ERROR = "error"


@dataclass(frozen=True)
class QueryContext:
    """What was actually requested/resolved, echoed back for the caller.

    QueryRequest supports multiple metrics in one request, so `metrics`
    is plural here (unlike the single "metric" field in the Phase 9.6
    doc's sketch) — this stays consistent with the real QueryRequest
    contract instead of silently dropping multi-metric support.
    """

    metrics: list[str] = field(default_factory=list)
    dimensions: list[str] = field(default_factory=list)
    filters: list[dict[str, Any]] = field(default_factory=list)
    time_grain: Union[str, None] = None


@dataclass(frozen=True)
class MetricMetadata:
    """Registry-sourced metadata for one requested metric.

    Always comes from the metric registry (see response/builder.py) —
    never hardcoded here or anywhere else in this layer. The registry
    is the one source of truth for labels and units.
    """

    metric: str
    label: str
    unit: Union[str, None] = None


@dataclass(frozen=True)
class ResponseMetadata:
    """Result-shape metadata: what the requested metrics mean, and
    how many rows came back."""

    metrics: list[MetricMetadata] = field(default_factory=list)
    row_count: int = 0


@dataclass(frozen=True)
class AnalyticalError:
    """A stable, code-based error description.

    `stage` mirrors AnalyticalQueryResponse.error_stage from the
    service layer (e.g. "semantic_resolution", "query_execution") so
    a caller can tell which part of the pipeline failed without
    parsing `message`.
    """

    code: str
    message: str
    stage: Union[str, None] = None


@dataclass(frozen=True)
class AnalyticalResponse:
    """The top-level public analytical response contract.

    Invariant, enforced at construction: success=True implies error is
    None, and success=False implies error is set. This is the
    "success = True + error must be None" rule from the Phase 9.6 spec
    — checked here so it can never silently drift, rather than relying
    on every caller of the builder getting it right by convention.
    """

    success: bool
    status: AnalyticalResponseStatus
    query: Union[QueryContext, None] = None
    metadata: Union[ResponseMetadata, None] = None
    data: list[dict[str, Any]] = field(default_factory=list)
    error: Union[AnalyticalError, None] = None

    def __post_init__(self) -> None:
        if self.success and self.error is not None:
            raise ValueError(
                "AnalyticalResponse is inconsistent: success=True but error is set."
            )
        if not self.success and self.error is None:
            raise ValueError(
                "AnalyticalResponse is inconsistent: success=False but error is None."
            )

    def to_dict(self) -> dict[str, Any]:
        """JSON-friendly representation matching the Phase 9.6 contract."""

        return {
            "success": self.success,
            "status": self.status.value,
            "query": _query_context_to_dict(self.query),
            "metadata": _metadata_to_dict(self.metadata),
            "data": self.data,
            "error": _error_to_dict(self.error),
        }


def _query_context_to_dict(
    context: Union[QueryContext, None],
) -> Union[dict[str, Any], None]:
    if context is None:
        return None
    return {
        "metrics": context.metrics,
        "dimensions": context.dimensions,
        "filters": context.filters,
        "time_grain": context.time_grain,
    }


def _metadata_to_dict(
    metadata: Union[ResponseMetadata, None],
) -> Union[dict[str, Any], None]:
    if metadata is None:
        return None
    return {
        "metrics": [
            {"metric": m.metric, "label": m.label, "unit": m.unit}
            for m in metadata.metrics
        ],
        "row_count": metadata.row_count,
    }


def _error_to_dict(
    error: Union[AnalyticalError, None],
) -> Union[dict[str, Any], None]:
    if error is None:
        return None
    return {
        "code": error.code,
        "message": error.message,
        "stage": error.stage,
    }
