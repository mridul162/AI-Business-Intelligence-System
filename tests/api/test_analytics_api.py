from __future__ import annotations

from etl.analytics.query.models import QueryRequest
from etl.analytics.service.models import AnalyticalQueryResponse

from fastapi.testclient import TestClient

from api.app import create_app
from api.dependencies.analytics import get_analytics_service


class StubAnalyticsService:
    def __init__(self, response: AnalyticalQueryResponse) -> None:
        self.response = response
        self.questions: list[str] = []

    def query(self, text: str) -> AnalyticalQueryResponse:
        self.questions.append(text)
        return self.response


def make_client(service: StubAnalyticsService) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_analytics_service] = lambda: service
    return TestClient(app)


def test_health_endpoint() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_analytics_query_success_uses_dependency_service() -> None:
    service = StubAnalyticsService(
        AnalyticalQueryResponse(
            success=True,
            data=[{"gross_sales": 15990.0}],
            row_count=1,
            columns=["gross_sales"],
            query=QueryRequest(metrics=("gross_sales",)),
        )
    )
    client = make_client(service)

    response = client.post(
        "/analytics/query",
        json={"question": "What were total sales?"},
    )

    assert response.status_code == 200
    assert service.questions == ["What were total sales?"]
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
                {"metric": "gross_sales", "label": "Gross Sales", "unit": None}
            ],
            "row_count": 1,
        },
        "data": [{"gross_sales": 15990.0}],
        "error": None,
    }


def test_analytics_query_semantic_failure_returns_422() -> None:
    service = StubAnalyticsService(
        AnalyticalQueryResponse(
            success=False,
            error="unknown metric: foo",
            error_stage="semantic_resolution",
        )
    )
    client = make_client(service)

    response = client.post("/analytics/query", json={"question": "what is foo?"})

    assert response.status_code == 422
    assert response.json()["detail"] == {
        "code": "SEMANTIC_RESOLUTION_FAILED",
        "message": "unknown metric: foo",
        "stage": "semantic_resolution",
    }


def test_analytics_query_execution_failure_hides_internal_message() -> None:
    service = StubAnalyticsService(
        AnalyticalQueryResponse(
            success=False,
            error="connection refused at 10.0.0.5",
            error_stage="query_execution",
        )
    )
    client = make_client(service)

    response = client.post("/analytics/query", json={"question": "total sales"})

    assert response.status_code == 502
    assert response.json()["detail"] == {
        "code": "QUERY_EXECUTION_FAILED",
        "message": "Unable to execute the analytical query.",
        "stage": "query_execution",
    }
