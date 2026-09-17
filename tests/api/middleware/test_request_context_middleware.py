from fastapi import FastAPI
from fastapi.testclient import TestClient

from uuid import UUID

from api.middleware.request_context import RequestContextMiddleware
from etl.analytics.context.request_context import get_request_context


def test_request_context_middleware_adds_request_id() -> None:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)

    @app.get("/test")
    def test_endpoint():
        context = get_request_context()

        assert context is not None

        return {
            "request_id": str(context.request_id),
        }

    client = TestClient(app)

    response = client.get("/test")

    assert response.status_code == 200

    header_request_id = response.headers["X-Request-ID"]
    body_request_id = response.json()["request_id"]

    assert header_request_id == body_request_id


def test_each_request_gets_a_unique_request_id() -> None:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)

    @app.get("/test")
    def test_endpoint():
        return {"ok": True}

    client = TestClient(app)

    first = client.get("/test")
    second = client.get("/test")

    first_id = first.headers["X-Request-ID"]
    second_id = second.headers["X-Request-ID"]

    assert first_id != second_id



def test_request_id_is_valid_uuid() -> None:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)

    @app.get("/test")
    def test_endpoint():
        return {"ok": True}

    client = TestClient(app)

    response = client.get("/test")

    request_id = response.headers["X-Request-ID"]

    UUID(request_id)

def test_request_context_is_cleared_after_request() -> None:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)

    @app.get("/test")
    def test_endpoint():
        assert get_request_context() is not None
        return {"ok": True}

    client = TestClient(app)

    response = client.get("/test")

    assert response.status_code == 200
    assert get_request_context() is None


def test_request_context_is_cleared_after_exception() -> None:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)

    @app.get("/test")
    def test_endpoint():
        assert get_request_context() is not None
        raise RuntimeError("test failure")

    client = TestClient(app)

    try:
        client.get("/test")
    except RuntimeError:
        pass

    assert get_request_context() is None