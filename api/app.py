"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI

from api.routes.analytics import router as analytics_router

from api.middleware.request_context import RequestContextMiddleware
from api.middleware.rate_limit import RateLimitMiddleware
from etl.analytics.config import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(title="AI Business Intelligence API")

    if settings is None:
        app.add_middleware(RateLimitMiddleware)
    else:
        app.add_middleware(
            RateLimitMiddleware,
            requests=settings.rate_limit_requests,
            window_seconds=settings.rate_limit_window_seconds,
            burst=settings.rate_limit_burst,
        )
    # Starlette applies the most recently added middleware outermost, so the
    # request context wraps rate limiting and labels rejected requests too.
    app.add_middleware(RequestContextMiddleware)

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(analytics_router)
    return app


app = create_app()
