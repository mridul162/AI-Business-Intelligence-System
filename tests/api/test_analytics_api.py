from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from api.app import create_app
from api.dependencies.analytics import get_analytics_application
from etl.analytics.executor.errors import QueryExecutionFailedError
from etl.analytics.response.models import (
    AnalyticalResponse,
    AnalyticalResponseStatus,
    MetricMetadata,
    QueryContext,
    ResponseMetadata,
)
from etl.analytics.semantic.models import ResolutionResult, SemanticResolutionError


class StubAnalyticsApplication:
    """Minimal application stub for API dependency tests."""

    def __init__(self, response: AnalyticalResponse) -> None:
        self.response = response
        self.questions: list[str] = []

    def query(self, text: str) -> AnalyticalResponse:
        self.questions.append(text)
        return self.response


def make_client(application: Any) -> TestClient:
    """Create a test client with the analytics application overridden."""
    app = create_app()
    app.dependency_overrides[get_analytics_application] = lambda: application
    return TestClient(app)


def test_health_endpoint() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_analytics_query_success_uses_application_dependency() -> None:
    application = StubAnalyticsApplication(
        AnalyticalResponse(
            success=True,
            status=AnalyticalResponseStatus.SUCCESS,
            query=QueryContext(
                metrics=["gross_sales"],
            ),
            metadata=ResponseMetadata(
                metrics=[
                    MetricMetadata(
                        metric="gross_sales",
                        label="Gross Sales",
                    )
                ],
                row_count=1,
            ),
            data=[
                {
                    "gross_sales": 15990.0,
                }
            ],
        )
    )

    client = make_client(application)

    response = client.post(
        "/analytics/query",
        json={"question": "What were total sales?"},
    )

    assert response.status_code == 200
    assert application.questions == ["What were total sales?"]

    assert response.json() == {
        "success": True,
        "status": "success",
        "query": {
            "metrics": ["gross_sales"],
            "dimensions": [],
            "filters": [],
            "time_grain": None,
        },
        "metadata": {
            "metrics": [
                {
                    "metric": "gross_sales",
                    "label": "Gross Sales",
                    "unit": None,
                }
            ],
            "row_count": 1,
        },
        "data": [
            {
                "gross_sales": 15990.0,
            }
        ],
        "error": None,
    }


def test_analytics_query_semantic_failure_returns_422() -> None:
    class FailingApplication:
        def query(self, text: str) -> AnalyticalResponse:
            raise SemanticResolutionError(
                (
                    ResolutionResult.not_found(
                        "metric",
                        "foo",
                        "unknown metric: foo",
                    ),
                )
            )

    client = make_client(FailingApplication())

    response = client.post(
        "/analytics/query",
        json={"question": "what is foo?"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == {
        "code": "SEMANTIC_RESOLUTION_FAILED",
        "message": (
            "Semantic resolution failed (1 issue(s)): "
            "metric: unknown metric: foo"
        ),
        "stage": "semantic_resolution",
    }


def test_analytics_query_execution_failure_hides_internal_message() -> None:
    class FailingApplication:
        def query(self, text: str) -> AnalyticalResponse:
            raise QueryExecutionFailedError(
                "connection refused at 10.0.0.5"
            )

    client = make_client(FailingApplication())

    response = client.post(
        "/analytics/query",
        json={"question": "total sales"},
    )

    assert response.status_code == 502
    assert response.json()["detail"] == {
        "code": "QUERY_EXECUTION_FAILED",
        "message": "Unable to execute the analytical query.",
        "stage": "query_execution",
    }