from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from api.dependencies.analytics import get_analytics_application
from api.security.authentication import AuthenticationService, TokenService
from api.security.models import InMemoryIdentityStore, Role, Tenant, User
from api.security.password import hash_password, verify_password
from etl.analytics.response.models import AnalyticalResponse, AnalyticalResponseStatus


def make_identity() -> tuple[InMemoryIdentityStore, User, TokenService]:
    tenant = Tenant(id=uuid4(), name="Tenant A")
    user = User(
        id=uuid4(),
        email="analyst@example.com",
        password_hash=hash_password("correct-password"),
        tenant_id=tenant.id,
        role=Role.ANALYST,
    )
    store = InMemoryIdentityStore(users=(user,), tenants=(tenant,))
    return store, user, TokenService("x" * 32)


def test_unauthenticated_request_is_rejected_before_analytics_dependency_runs() -> None:
    store, user, token_service = make_identity()
    app = create_app(identity_store=store, token_service=token_service)

    def _factory_should_not_run():
        raise AssertionError(
            "get_analytics_application resolved before authentication"
        )

    app.dependency_overrides[get_analytics_application] = _factory_should_not_run
    client = TestClient(app)

    response = client.post("/analytics/query", json={"question": "sales"})

    assert response.status_code == 401


def test_authenticated_request_actually_reaches_analytics_application() -> None:
    store, user, token_service = make_identity()
    app = create_app(identity_store=store, token_service=token_service)

    class RecordingApplication:
        def __init__(self):
            self.called_with: list[str] = []

        def query(self, question: str):
            self.called_with.append(question)
            return AnalyticalResponse(
                success=True,
                status=AnalyticalResponseStatus.SUCCESS,
            )

    application = RecordingApplication()
    app.dependency_overrides[get_analytics_application] = lambda: application
    client = TestClient(app)

    token = token_service.create_access_token(user)
    response = client.post(
        "/analytics/query",
        json={"question": "sales"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert application.called_with == ["sales"]