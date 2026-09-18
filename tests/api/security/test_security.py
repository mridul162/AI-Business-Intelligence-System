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


def test_password_hashing_verifies_only_the_original_password() -> None:
    password_hash = hash_password("correct-password")

    assert verify_password("correct-password", password_hash)
    assert not verify_password("wrong-password", password_hash)
    assert not verify_password("", password_hash)
    with pytest.raises(ValueError):
        hash_password("")


def test_authentication_rejects_inactive_users() -> None:
    store, user, token_service = make_identity()
    inactive = User(**{**user.__dict__, "is_active": False})
    store.users[user.id] = inactive

    with pytest.raises(Exception):
        AuthenticationService(store, token_service).authenticate(
            user.email,
            "correct-password",
        )


def test_token_rejects_tampering_and_expiration() -> None:
    store, user, token_service = make_identity()
    token = token_service.create_access_token(user)
    tampered = token[:-1] + ("a" if token[-1] != "a" else "b")

    with pytest.raises(Exception):
        token_service.decode_access_token(tampered)

    expired = token_service.create_access_token(user, expires_minutes=-1)
    with pytest.raises(Exception):
        token_service.decode_access_token(expired)


def test_analytics_requires_authentication_and_accepts_valid_token() -> None:
    store, user, token_service = make_identity()
    app = create_app(identity_store=store)

    class StubApplication:
        def query(self, question: str):
            raise RuntimeError("authenticated request reached analytics")

    app.dependency_overrides[get_analytics_application] = StubApplication
    client = TestClient(app)

    missing = client.post("/analytics/query", json={"question": "sales"})
    assert missing.status_code == 401

    token = token_service.create_access_token(user)
    try:
        client.post(
            "/analytics/query",
            json={"question": "sales"},
            headers={"Authorization": f"Bearer {token}"},
        )
    except RuntimeError as exc:
        assert str(exc) == "authenticated request reached analytics"


def test_login_endpoint_issues_bearer_token() -> None:
    store, user, _ = make_identity()
    app = create_app(identity_store=store)
    client = TestClient(app)

    response = client.post(
        "/auth/token",
        json={"email": user.email, "password": "correct-password"},
    )

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]