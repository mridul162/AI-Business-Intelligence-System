"""Regression tests for the generated OpenAPI contract.

These don't test route behavior (see test_analytics_api.py for that) --
they test that the *documentation* stays accurate as routes change.
"""
from __future__ import annotations

from api.app import create_app
from api.security.models import InMemoryIdentityStore


def get_openapi_schema() -> dict:
    app = create_app(identity_store=InMemoryIdentityStore(users=(), tenants=()))
    return app.openapi()


def test_analytics_query_documents_all_real_failure_statuses() -> None:
    schema = get_openapi_schema()
    responses = schema["paths"]["/analytics/query"]["post"]["responses"]

    for status_code in ("200", "400", "401", "422", "500", "502"):
        assert status_code in responses, f"missing documented status {status_code}"


def test_analytics_query_requires_bearer_auth_in_openapi() -> None:
    schema = get_openapi_schema()
    operation = schema["paths"]["/analytics/query"]["post"]
    assert operation.get("security") == [{"HTTPBearer": []}]


def test_auth_token_documents_401() -> None:
    schema = get_openapi_schema()
    responses = schema["paths"]["/auth/token"]["post"]["responses"]
    assert "401" in responses


def test_auth_token_has_no_security_requirement() -> None:
    schema = get_openapi_schema()
    operation = schema["paths"]["/auth/token"]["post"]
    assert "security" not in operation


def test_analytical_response_status_is_a_closed_enum_in_openapi() -> None:
    schema = get_openapi_schema()
    status_schema = schema["components"]["schemas"]["AnalyticalResponseSchema"][
        "properties"
    ]["status"]
    # Pydantic emits a $ref to the enum's own schema component rather than
    # inlining it -- resolve one level if needed.
    if "$ref" in status_schema:
        ref_name = status_schema["$ref"].rsplit("/", 1)[-1]
        status_schema = schema["components"]["schemas"][ref_name]
    assert set(status_schema["enum"]) == {"success", "empty", "error"}


def test_health_endpoint_is_undocumented_for_auth() -> None:
    schema = get_openapi_schema()
    operation = schema["paths"]["/health"]["get"]
    assert "security" not in operation