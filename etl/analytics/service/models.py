"""
Schema for the end-to-end orchestration response.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Union

from etl.analytics.query.models import QueryRequest


@dataclass(frozen=True)
class AnalyticalQueryResponse:
    """Result returned by AnalyticalQueryService.query().

    A failed run (at any stage) still returns one of these, with
    success=False and `error`/`error_stage` set, rather than raising —
    callers (an API layer, an LLM tool result, a CLI) get a single,
    uniform shape to branch on instead of needing to catch exceptions
    from several different stages.
    """

    success: bool
    data: list[dict[str, Any]] = field(default_factory=list)
    row_count: int = 0
    columns: list[str] = field(default_factory=list)
    query: Union[QueryRequest, None] = None
    error: Union[str, None] = None
    error_stage: Union[str, None] = None

    def to_dict(self) -> dict[str, Any]:
        """JSON-friendly representation, matching the shape sketched
        in the Phase 9.5 spec: success/query/data/row_count."""

        return {
            "success": self.success,
            "query": _summarize_query_request(self.query),
            "data": self.data,
            "row_count": self.row_count,
            "columns": self.columns,
            "error": self.error,
            "error_stage": self.error_stage,
        }


def _summarize_query_request(
    request: Union[QueryRequest, None],
) -> Union[dict[str, Any], None]:
    """Render a QueryRequest as a small JSON-friendly summary.

    Only includes fields that were actually set, so a simple
    "total sales" query doesn't show a wall of nulls.
    """

    if request is None:
        return None

    summary: dict[str, Any] = {
        "metrics": list(request.metrics),
    }

    if request.dimensions:
        summary["dimensions"] = list(request.dimensions)
    if request.time_grain is not None:
        summary["time_grain"] = request.time_grain.value
    if request.filters:
        summary["filters"] = [
            {
                "dimension": f.dimension,
                "operator": f.operator.value,
                "value": f.value,
            }
            for f in request.filters
        ]
    if request.date_from is not None:
        summary["date_from"] = request.date_from.isoformat()
    if request.date_to is not None:
        summary["date_to"] = request.date_to.isoformat()
    if request.order_by:
        summary["order_by"] = [
            {"field": o.field, "direction": o.direction}
            for o in request.order_by
        ]
    if request.limit is not None:
        summary["limit"] = request.limit

    return summary
