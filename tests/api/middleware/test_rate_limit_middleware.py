from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.middleware.rate_limit import InMemoryRateLimiter, RateLimitMiddleware


def test_limiter_enforces_burst_and_separates_clients() -> None:
    limiter = InMemoryRateLimiter(requests=1, window_seconds=60, burst=2)

    assert limiter.allow("client-a")[0] is True
    assert limiter.allow("client-a")[0] is True
    assert limiter.allow("client-a")[0] is False
    assert limiter.allow("client-b")[0] is True


def test_middleware_returns_429_with_retry_header() -> None:
    app = FastAPI()
    app.add_middleware(
        RateLimitMiddleware,
        requests=1,
        window_seconds=60,
        burst=1,
    )

    @app.get("/test")
    def test_endpoint() -> dict[str, bool]:
        return {"ok": True}

    client = TestClient(app)
    assert client.get("/test").status_code == 200
    response = client.get("/test")

    assert response.status_code == 429
    assert response.headers["Retry-After"]
    assert response.json()["detail"]["code"] == "RATE_LIMIT_EXCEEDED"