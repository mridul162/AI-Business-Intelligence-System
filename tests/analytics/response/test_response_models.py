"""Unit tests for etl.analytics.response.models."""

from __future__ import annotations

import pytest

from etl.analytics.response.models import (
    AnalyticalError,
    AnalyticalResponse,
    AnalyticalResponseStatus,
    MetricMetadata,
    QueryContext,
    ResponseMetadata,
)


class TestSuccessErrorInvariant:
    def test_success_true_with_error_raises(self) -> None:
        with pytest.raises(ValueError):
            AnalyticalResponse(
                success=True,
                status=AnalyticalResponseStatus.SUCCESS,
                error=AnalyticalError(code="X", message="should not happen"),
            )

    def test_success_false_without_error_raises(self) -> None:
        with pytest.raises(ValueError):
            AnalyticalResponse(
                success=False,
                status=AnalyticalResponseStatus.ERROR,
            )

    def test_success_true_without_error_is_valid(self) -> None:
        response = AnalyticalResponse(
            success=True,
            status=AnalyticalResponseStatus.EMPTY,
        )
        assert response.error is None

    def test_success_false_with_error_is_valid(self) -> None:
        response = AnalyticalResponse(
            success=False,
            status=AnalyticalResponseStatus.ERROR,
            error=AnalyticalError(code="QUERY_EXECUTION_FAILED", message="db down"),
        )
        assert response.error is not None


class TestToDict:
    def test_success_response_to_dict(self) -> None:
        response = AnalyticalResponse(
            success=True,
            status=AnalyticalResponseStatus.SUCCESS,
            query=QueryContext(metrics=["total_sales"], dimensions=["month"]),
            metadata=ResponseMetadata(
                metrics=[MetricMetadata(metric="total_sales", label="Total Sales", unit="BDT")],
                row_count=2,
            ),
            data=[{"month": "2026-08", "total_sales": 15990.0}],
        )

        payload = response.to_dict()

        assert payload["success"] is True
        assert payload["status"] == "success"
        assert payload["query"] == {
            "metrics": ["total_sales"],
            "dimensions": ["month"],
            "filters": [],
            "time_grain": None,
        }
        assert payload["metadata"] == {
            "metrics": [{"metric": "total_sales", "label": "Total Sales", "unit": "BDT"}],
            "row_count": 2,
        }
        assert payload["data"] == [{"month": "2026-08", "total_sales": 15990.0}]
        assert payload["error"] is None

    def test_error_response_to_dict(self) -> None:
        response = AnalyticalResponse(
            success=False,
            status=AnalyticalResponseStatus.ERROR,
            error=AnalyticalError(
                code="QUERY_EXECUTION_FAILED",
                message="db down",
                stage="query_execution",
            ),
        )

        payload = response.to_dict()

        assert payload["success"] is False
        assert payload["status"] == "error"
        assert payload["query"] is None
        assert payload["metadata"] is None
        assert payload["data"] == []
        assert payload["error"] == {
            "code": "QUERY_EXECUTION_FAILED",
            "message": "db down",
            "stage": "query_execution",
        }
