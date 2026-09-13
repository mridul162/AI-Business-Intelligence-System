"""
Builds the public AnalyticalResponse from the analytical pipeline result.

This module is deliberately narrow. It does not:
- execute SQL
- access PostgreSQL
- resolve semantic aliases
- parse natural language
- call an LLM
- perform query planning or execution

It only transforms:
    AnalyticalQueryRequest + AnalyticalResult
into:
    AnalyticalResponse

Metric metadata comes from the metric registry and is injected as a
callable so tests can substitute a fake registry lookup.

AnalyticalResult contains only the executed analytical result
(columns, rows, row_count, merge_strategy), so the original
AnalyticalQueryRequest is supplied separately to reconstruct the
public query context and metric metadata.
"""

from __future__ import annotations

from typing import Callable

from etl.analytics.metrics.definitions import MetricDefinition
from etl.analytics.metrics.registry import get_metric as _default_get_metric
from etl.analytics.response.models import (
    AnalyticalResponse,
    AnalyticalResponseStatus,
    MetricMetadata,
    QueryContext,
    ResponseMetadata,
)
from etl.analytics.schemas import AnalyticalQueryRequest
from etl.analytics.orchestration import AnalyticalResult


class AnalyticalResponseBuilder:
    """Builds a public AnalyticalResponse from an analytical result."""

    def __init__(
        self,
        get_metric: Callable[[str], MetricDefinition] = _default_get_metric,
    ) -> None:
        self.get_metric = get_metric

    def build(
        self,
        request: AnalyticalQueryRequest,
        result: AnalyticalResult,
    ) -> AnalyticalResponse:
        """Build the stable public response contract."""

        query_context = self._build_query_context(request)
        metadata = self._build_metadata(request, result)

        status = (
            AnalyticalResponseStatus.SUCCESS
            if result.row_count > 0
            else AnalyticalResponseStatus.EMPTY
        )

        return AnalyticalResponse(
            success=True,
            status=status,
            query=query_context,
            metadata=metadata,
            data=list(result.rows),
        )

    def _build_query_context(
        self,
        request: AnalyticalQueryRequest,
    ) -> QueryContext:
        """Build the public representation of the resolved request."""

        metrics = [request.metric, *request.additional_metrics]

        return QueryContext(
            metrics=metrics,
            dimensions=list(request.dimensions),
            filters=[
                {
                    "field": f.dimension,
                    "operator": f.operator,
                    "value": f.value,
                }
                for f in request.filters
            ],
            time_grain=request.time_grain,
        )

    def _build_metadata(
        self,
        request: AnalyticalQueryRequest,
        result: AnalyticalResult,
    ) -> ResponseMetadata:
        """Attach registry metadata and result row count."""

        metric_names = [request.metric, *request.additional_metrics]

        metrics_metadata = [
            self._resolve_metric_metadata(metric_name)
            for metric_name in metric_names
        ]

        return ResponseMetadata(
            metrics=metrics_metadata,
            row_count=result.row_count,
        )

    def _resolve_metric_metadata(
        self,
        metric_name: str,
    ) -> MetricMetadata:
        """Resolve public metadata from the metric registry."""

        definition = self.get_metric(metric_name)

        return MetricMetadata(
            metric=definition.name,
            label=definition.display_name,
            # MetricDefinition currently has no unit/currency field.
            unit=None,
        )