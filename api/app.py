"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI

from api.routes.analytics import router as analytics_router

from api.middleware.request_context import RequestContextMiddleware


def create_app() -> FastAPI:
    app = FastAPI(title="AI Business Intelligence API")

    app.add_middleware(RequestContextMiddleware)

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(analytics_router)
    return app


app = create_app()
