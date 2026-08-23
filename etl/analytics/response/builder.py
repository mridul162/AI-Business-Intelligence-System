"""
Builds the public AnalyticalResponse from the service layer's raw result.

Deliberately narrow: this module does not execute SQL, call Postgres,
resolve aliases, parse natural language, or call an LLM. It only
reshapes an already-complete AnalyticalQueryResponse (from
etl.analytics.service) into the stable AnalyticalResponse contract,
attaching registry-sourced metric metadata along the way.

Metric metadata comes from etl.analytics.metrics.registry.get_metric,
a plain module-level function (not a class instance), matching your
actual registry.py. It's injected as a callable rather than imported
and called directly, so tests can substitute a fake without touching
the real METRIC_REGISTRY.

Your MetricDefinition (metrics/definitions.py) has no `unit`/currency
field, so MetricMetadata.unit is always None for now — add a `unit`
field to MetricDefinition and wire it through here once that concept
exists upstream, rather than fabricating a currency here.

Financial/type serialization policy: values in `service_result.data`
have already been passed through etl.analytics.execution.serializer
(Decimal -> float, date/datetime -> ISO string, UUID -> string) by the
time they reach this layer, since AnalyticalQueryResponse.data comes
straight from QueryExecutionResult.rows. This builder does not
re-serialize rows — it passes them through unchanged, preserving the
original query output field names (no renaming to display labels; that
belongs to a future presentation layer). If your project needs
Decimal-as-string instead of Decimal-as-float for exactness, that
policy change belongs in the execution-layer serializer, not here —
keeping one serialization point avoids two layers disagreeing.
"""

from __future__ import annotations

from typing import Callable, Union

from etl.analytics.metrics.definitions import MetricDefinition
from etl.analytics.metrics.registry import get_metric as _default_get_metric
from etl.analytics.query.models import QueryRequest
from etl.analytics.response.models import (
    AnalyticalError,
    AnalyticalResponse,
    AnalyticalResponseStatus,
    MetricMetadata,
    QueryContext,
    ResponseMetadata,
)
from etl.analytics.service.models import AnalyticalQueryResponse

_ERROR_CODES_BY_STAGE = {
    "semantic_resolution": "SEMANTIC_RESOLUTION_FAILED",
    "query_building": "QUERY_BUILD_FAILED",
    "query_validation": "QUERY_VALIDATION_FAILED",
    "query_execution": "QUERY_EXECUTION_FAILED",
}
_UNKNOWN_ERROR_CODE = "UNKNOWN_ERROR"


class AnalyticalResponseBuilder:
    """Turns an AnalyticalQueryResponse into a public AnalyticalResponse."""

    def __init__(
        self,
        get_metric: Callable[[str], MetricDefinition] = _default_get_metric,
    ) -> None:
        self.get_metric = get_metric

    def build(
        self,
        service_result: AnalyticalQueryResponse,
    ) -> AnalyticalResponse:
        if not service_result.success:
            return self._build_error_response(service_result)
        return self._build_data_response(service_result)

    def _build_error_response(
        self,
        service_result: AnalyticalQueryResponse,
    ) -> AnalyticalResponse:
        error = AnalyticalError(
            code=_ERROR_CODES_BY_STAGE.get(
                service_result.error_stage or "", _UNKNOWN_ERROR_CODE
            ),
            message=service_result.error or "Unable to execute the analytical query.",
            stage=service_result.error_stage,
        )
        return AnalyticalResponse(
            success=False,
            status=AnalyticalResponseStatus.ERROR,
            error=error,
        )

    def _build_data_response(
        self,
        service_result: AnalyticalQueryResponse,
    ) -> AnalyticalResponse:
        query_context = self._build_query_context(service_result.query)
        metadata = self._build_metadata(service_result)

        status = (
            AnalyticalResponseStatus.SUCCESS
            if service_result.row_count > 0
            else AnalyticalResponseStatus.EMPTY
        )

        return AnalyticalResponse(
            success=True,
            status=status,
            query=query_context,
            metadata=metadata,
            data=service_result.data,
        )

    def _build_query_context(
        self,
        request: Union[QueryRequest, None],
    ) -> QueryContext:
        if request is None:
            return QueryContext()

        return QueryContext(
            metrics=list(request.metrics),
            dimensions=list(request.dimensions),
            filters=[
                {
                    "field": f.dimension,
                    "operator": f.operator.value,
                    "value": f.value,
                }
                for f in request.filters
            ],
            time_grain=request.time_grain,
        )

    def _build_metadata(
        self,
        service_result: AnalyticalQueryResponse,
    ) -> ResponseMetadata:
        metric_names = (
            service_result.query.metrics if service_result.query else ()
        )

        metrics_metadata = [
            self._resolve_metric_metadata(metric_name)
            for metric_name in metric_names
        ]

        return ResponseMetadata(
            metrics=metrics_metadata,
            row_count=service_result.row_count,
        )

    def _resolve_metric_metadata(self, metric_name: str) -> MetricMetadata:
        definition = self.get_metric(metric_name)
        return MetricMetadata(
            metric=definition.name,
            label=definition.display_name,
            # MetricDefinition has no unit/currency field today.
            unit=None,
        )
