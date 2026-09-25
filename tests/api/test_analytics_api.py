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
from etl.analytics.merger.errors import ResultMergeError


class StubAnalyticsApplication:
    """Minimal application stub for API dependency tests."""

    def __init__(self, response: AnalyticalResponse) -> None:
        self.response = response
        self.questions: list[str] = []

    def query(self, text: str) -> AnalyticalResponse:
        self.questions.append(text)
        return self.response

class UnexpectedApplication:
    def query(self, text: str) -> AnalyticalResponse:
        raise AssertionError(
            "AnalyticsApplication should not be called."
        )


def make_client(application: Any) -> TestClient:
    """Create a test client with the analytics application overridden."""
    app = create_app(auth_enabled=False)
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


def test_analytics_query_rejects_empty_question() -> None:
    client = make_client(
        StubAnalyticsApplication(
            AnalyticalResponse(
                success=True,
                status=AnalyticalResponseStatus.SUCCESS,
            )
        )
    )

    response = client.post(
        "/analytics/query",
        json={"question": ""},
    )

    assert response.status_code == 422


def test_analytics_query_rejects_missing_question() -> None:
    client = make_client(
        StubAnalyticsApplication(
            AnalyticalResponse(
                success=True,
                status=AnalyticalResponseStatus.SUCCESS,
            )
        )
    )

    response = client.post(
        "/analytics/query",
        json={},
    )

    assert response.status_code == 422


def test_analytics_query_rejects_question_exceeding_max_length() -> None:
    client = make_client(
        StubAnalyticsApplication(
            AnalyticalResponse(
                success=True,
                status=AnalyticalResponseStatus.SUCCESS,
            )
        )
    )

    response = client.post(
        "/analytics/query",
        json={
            "question": "a" * 2001,
        },
    )

    assert response.status_code == 422


def test_analytics_query_strips_question_whitespace() -> None:
    application = StubAnalyticsApplication(
        AnalyticalResponse(
            success=True,
            status=AnalyticalResponseStatus.SUCCESS,
        )
    )

    client = make_client(application)

    response = client.post(
        "/analytics/query",
        json={
            "question": "  What were total sales?  ",
        },
    )

    assert response.status_code == 200
    assert application.questions == ["What were total sales?"]


def test_analytics_query_rejects_whitespace_only_question() -> None:
    client = make_client(UnexpectedApplication())

    response = client.post(
        "/analytics/query",
        json={"question": "   "},
    )

    assert response.status_code == 422


def test_analytics_query_merge_failure_returns_500():
    """Result-merging failures are exposed as a stable 500 API error."""

    class FailingAnalyticsApplication:
        def query(self, question: str):
            raise ResultMergeError("duplicate merge key: internal detail")

    client = TestClient(create_app(auth_enabled=False))
    client.app.dependency_overrides[get_analytics_application] = ( # type: ignore
        lambda: FailingAnalyticsApplication()
    )

    response = client.post(
        "/analytics/query",
        json={"question": "Compare sales and expenses"},
    )

    assert response.status_code == 500

    body = response.json()
    assert body["detail"]["code"] == "RESULT_MERGE_FAILED"
    assert body["detail"]["message"] == (
        "Failed to combine analytical query results."
    )
    assert body["detail"]["stage"] == "result_merging"
    assert "duplicate merge key" not in body["detail"]["message"]


def test_analytics_query_unexpected_error_returns_500():
    """Unexpected application failures are converted to a generic 500 error."""

    class FailingAnalyticsApplication:
        def query(self, question: str):
            raise RuntimeError("database password=super-secret")

    client = TestClient(create_app(auth_enabled=False))
    client.app.dependency_overrides[get_analytics_application] = ( # type: ignore
        lambda: FailingAnalyticsApplication()
    )

    response = client.post(
        "/analytics/query",
        json={"question": "What is our net sales?"},
    )

    assert response.status_code == 500

    body = response.json()
    assert body["detail"]["code"] == "INTERNAL_SERVER_ERROR"
    assert body["detail"]["message"] == (
        "An unexpected internal error occurred."
    )
    assert body["detail"]["stage"] == "internal"

    # Internal exception details must never reach the API client.
    assert "database password" not in str(body)
    assert "super-secret" not in str(body)


def test_analytics_query_unexpected_error_does_not_expose_exception_details():
    """Generic 500 responses must not leak the original exception message."""

    class FailingAnalyticsApplication:
        def query(self, question: str):
            raise ValueError(
                "SQL connection failed: host=internal-db password=secret123"
            )

    client = TestClient(create_app(auth_enabled=False))
    client.app.dependency_overrides[get_analytics_application] = ( # type: ignore
        lambda: FailingAnalyticsApplication()
    )

    response = client.post(
        "/analytics/query",
        json={"question": "What were our sales yesterday?"},
    )

    assert response.status_code == 500

    body = response.json()

    assert body["detail"]["code"] == "INTERNAL_SERVER_ERROR"
    assert body["detail"]["message"] == (
        "An unexpected internal error occurred."
    )

    leaked_body = str(body)
    assert "internal-db" not in leaked_body
    assert "secret123" not in leaked_body
    assert "SQL connection failed" not in leaked_body


def test_success_field_is_true_whenever_status_is_200() -> None:
    """Guards against a future change that returns success=False with a 200.

    AnalyticalResponseBuilder currently always sets success=True, so this
    can't fail today — it's here to catch a regression, not a live bug.
    """
    application = StubAnalyticsApplication(
        AnalyticalResponse(success=True, status=AnalyticalResponseStatus.EMPTY)
    )
    client = make_client(application)

    response = client.post("/analytics/query", json={"question": "no rows"})

    assert response.status_code == 200
    assert response.json()["success"] is True


def test_analytics_openapi_contract() -> None:
    """The analytics endpoint exposes its public API contract."""

    app = create_app(auth_enabled=True)
    schema = app.openapi()

    operation = schema["paths"]["/analytics/query"]["post"]

    assert operation["summary"] == "Execute an analytical query"

    assert operation["responses"]["200"]["content"]["application/json"][
        "schema"
    ]["$ref"] == "#/components/schemas/AnalyticalResponseSchema"

    assert "400" in operation["responses"]
    assert "401" in operation["responses"]
    assert "422" in operation["responses"]
    assert "500" in operation["responses"]
    assert "502" in operation["responses"]

    assert operation["security"] == [{"HTTPBearer": []}]


def test_analytics_openapi_error_response_schema() -> None:
    """The analytics error response has a stable public schema."""

    app = create_app(auth_enabled=True)
    schema = app.openapi()

    error_schema = schema["components"]["schemas"]["APIErrorResponseSchema"]

    assert error_schema["type"] == "object"
    assert error_schema["properties"]["detail"]["$ref"] == (
        "#/components/schemas/AnalyticalErrorSchema"
    )


def test_analytics_openapi_question_constraints() -> None:
    """The OpenAPI schema exposes the question validation contract."""

    app = create_app(auth_enabled=True)
    schema = app.openapi()

    question = schema["components"]["schemas"][
        "AnalyticalQuestionRequest"
    ]["properties"]["question"]

    assert question["type"] == "string"
    assert question["minLength"] == 1
    assert question["maxLength"] == 2000