"""Unit tests for etl.analytics.response.builder.

get_metric is faked as a simple dict lookup function — this proves the
builder's shaping logic without depending on the real, growing
METRIC_REGISTRY in etl/analytics/metrics/registry.py.
"""

from __future__ import annotations

from etl.analytics.metrics.definitions import MetricDefinition
from etl.analytics.query.models import (
    FilterOperator,
    QueryFilter,
    QueryRequest,
)
from etl.analytics.response.builder import AnalyticalResponseBuilder
from etl.analytics.response.models import AnalyticalResponseStatus
from etl.analytics.service.models import AnalyticalQueryResponse


def make_metric_definition(name: str, display_name: str) -> MetricDefinition:
    """Build a minimal-but-valid MetricDefinition for tests."""

    return MetricDefinition(
        name=name,
        display_name=display_name,
        description=f"{display_name} for tests.",
        source_view="analytics.v_test",
        aggregation="sum",
        expression=f"SUM({name})",
        filters=(),
        supported_dimensions=(),
        supported_time_grains=("daily", "weekly", "monthly", "quarterly", "yearly"),
        output_field=name,
    )


def make_fake_get_metric():
    definitions = {
        "total_sales": make_metric_definition("total_sales", "Total Sales"),
        "total_purchases": make_metric_definition("total_purchases", "Total Purchases"),
    }

    def get_metric(metric_name: str) -> MetricDefinition:
        return definitions[metric_name]

    return get_metric


class TestSuccessResponse:
    def test_rows_present_yields_success_status(self) -> None:
        builder = AnalyticalResponseBuilder(make_fake_get_metric())
        service_result = AnalyticalQueryResponse(
            success=True,
            data=[{"month": "2026-08", "total_sales": 15990.0}],
            row_count=1,
            columns=["month", "total_sales"],
            query=QueryRequest(metrics=("total_sales",), dimensions=("month",)),
        )

        response = builder.build(service_result)

        assert response.success is True
        assert response.status == AnalyticalResponseStatus.SUCCESS
        assert response.data == [{"month": "2026-08", "total_sales": 15990.0}]
        assert response.error is None

    def test_row_field_names_are_preserved_not_renamed(self) -> None:
        builder = AnalyticalResponseBuilder(make_fake_get_metric())
        service_result = AnalyticalQueryResponse(
            success=True,
            data=[{"month": "2026-08", "total_sales": 15990.0}],
            row_count=1,
            query=QueryRequest(metrics=("total_sales",), dimensions=("month",)),
        )

        response = builder.build(service_result)

        # Keys stay as the original query output field names —
        # no "Month" / "Total Sales" display-label renaming here.
        assert list(response.data[0].keys()) == ["month", "total_sales"]


class TestEmptyResponse:
    def test_zero_rows_yields_empty_status_and_is_still_success(self) -> None:
        builder = AnalyticalResponseBuilder(make_fake_get_metric())
        service_result = AnalyticalQueryResponse(
            success=True,
            data=[],
            row_count=0,
            columns=["total_sales"],
            query=QueryRequest(
                metrics=("total_sales",),
                filters=(
                    QueryFilter(
                        dimension="date",
                        operator=FilterOperator.BETWEEN,
                        value=["2025-01-01", "2025-01-31"],
                    ),
                ),
            ),
        )

        response = builder.build(service_result)

        assert response.success is True
        assert response.status == AnalyticalResponseStatus.EMPTY
        assert response.data == []
        assert response.error is None
        assert response.metadata.row_count == 0


class TestErrorResponse:
    def test_failed_service_result_yields_error_status(self) -> None:
        builder = AnalyticalResponseBuilder(make_fake_get_metric())
        service_result = AnalyticalQueryResponse(
            success=False,
            error="Failed to execute analytical query.",
            error_stage="query_execution",
        )

        response = builder.build(service_result)

        assert response.success is False
        assert response.status == AnalyticalResponseStatus.ERROR
        assert response.data == []
        assert response.error is not None
        assert response.error.code == "QUERY_EXECUTION_FAILED"
        assert response.error.stage == "query_execution"

    def test_error_response_has_no_query_or_metadata(self) -> None:
        builder = AnalyticalResponseBuilder(make_fake_get_metric())
        service_result = AnalyticalQueryResponse(
            success=False,
            error="unknown metric",
            error_stage="semantic_resolution",
        )

        response = builder.build(service_result)

        assert response.query is None
        assert response.metadata is None

    def test_unrecognized_stage_falls_back_to_unknown_error_code(self) -> None:
        builder = AnalyticalResponseBuilder(make_fake_get_metric())
        service_result = AnalyticalQueryResponse(
            success=False,
            error="something odd",
            error_stage=None,
        )

        response = builder.build(service_result)

        assert response.error.code == "UNKNOWN_ERROR"


class TestMetricMetadata:
    def test_metadata_uses_display_name_from_registry_not_hardcoded(self) -> None:
        builder = AnalyticalResponseBuilder(make_fake_get_metric())
        service_result = AnalyticalQueryResponse(
            success=True,
            data=[{"total_purchases": 500.0}],
            row_count=1,
            query=QueryRequest(metrics=("total_purchases",)),
        )

        response = builder.build(service_result)

        assert len(response.metadata.metrics) == 1
        metric_meta = response.metadata.metrics[0]
        assert metric_meta.metric == "total_purchases"
        assert metric_meta.label == "Total Purchases"

    def test_unit_is_none_since_metric_definition_has_no_unit_field(self) -> None:
        builder = AnalyticalResponseBuilder(make_fake_get_metric())
        service_result = AnalyticalQueryResponse(
            success=True,
            data=[{"total_sales": 15990.0}],
            row_count=1,
            query=QueryRequest(metrics=("total_sales",)),
        )

        response = builder.build(service_result)

        assert response.metadata.metrics[0].unit is None

    def test_multiple_metrics_each_resolve_independently(self) -> None:
        builder = AnalyticalResponseBuilder(make_fake_get_metric())
        service_result = AnalyticalQueryResponse(
            success=True,
            data=[{"total_sales": 15990.0, "total_purchases": 500.0}],
            row_count=1,
            query=QueryRequest(metrics=("total_sales", "total_purchases")),
        )

        response = builder.build(service_result)

        labels = {m.metric: m.label for m in response.metadata.metrics}
        assert labels == {
            "total_sales": "Total Sales",
            "total_purchases": "Total Purchases",
        }


class TestQueryContextPreservation:
    def test_preserves_metrics_dimensions_filters_time_grain(self) -> None:
        builder = AnalyticalResponseBuilder(make_fake_get_metric())
        service_result = AnalyticalQueryResponse(
            success=True,
            data=[{"customer_name": "Customer A", "total_sales": 5000.0}],
            row_count=1,
            query=QueryRequest(
                metrics=("total_sales",),
                dimensions=("customer_name",),
                time_grain="monthly",
                filters=(
                    QueryFilter(
                        dimension="region",
                        operator=FilterOperator.EQ,
                        value="Dhaka",
                    ),
                ),
            ),
        )

        response = builder.build(service_result)

        assert response.query.metrics == ["total_sales"]
        assert response.query.dimensions == ["customer_name"]
        assert response.query.time_grain == "monthly"
        assert response.query.filters == [
            {"field": "region", "operator": "eq", "value": "Dhaka"}
        ]

    def test_missing_query_context_falls_back_to_empty_context(self) -> None:
        builder = AnalyticalResponseBuilder(make_fake_get_metric())
        service_result = AnalyticalQueryResponse(
            success=True,
            data=[],
            row_count=0,
            query=None,
        )

        response = builder.build(service_result)

        assert response.query.metrics == []
        assert response.metadata.metrics == []


class TestRealRegistryIntegration:
    """A light smoke test against the actual METRIC_REGISTRY, so a typo
    in a real metric name (e.g. in a future semantic resolver) would
    surface here instead of only in production."""

    def test_uses_real_registry_by_default(self) -> None:
        builder = AnalyticalResponseBuilder()
        service_result = AnalyticalQueryResponse(
            success=True,
            data=[{"gross_sales": 15990.0}],
            row_count=1,
            query=QueryRequest(metrics=("gross_sales",)),
        )

        response = builder.build(service_result)

        assert response.metadata.metrics[0].label == "Gross Sales"
