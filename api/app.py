"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI

from api.routes.auth import router as auth_router
from api.routes.analytics import router as analytics_router

from api.middleware.request_context import RequestContextMiddleware
from api.middleware.rate_limit import RateLimitMiddleware
from api.security.authentication import AuthenticationService, TokenService
from api.security.models import InMemoryIdentityStore, IdentityStore
from api.security.repository import SqlAlchemyIdentityStore
from database.connection import get_sessionmaker
from etl.analytics.config import Settings
from etl.observability.logging import configure_logging


def create_app(
    settings: Settings | None = None,
    *,
    identity_store: IdentityStore | None = None,
    auth_enabled: bool | None = None,
) -> FastAPI:
    app = FastAPI(title="AI Business Intelligence API")
    configure_logging()

    configured_auth = settings.auth_enabled if settings is not None else True
    if (
        settings is not None
        and settings.environment == "production"
        and auth_enabled is False
    ):
        raise ValueError("Authentication cannot be disabled in production.")
    app.state.auth_enabled = (
        configured_auth if auth_enabled is None else auth_enabled
    )
    app.state.identity_store = identity_store or SqlAlchemyIdentityStore(
        lambda: get_sessionmaker()()
    )
    app.state.token_service = TokenService(
        settings.jwt_secret_key
        if settings is not None
        else "development-only-change-me-please-rotate"
    )
    app.state.auth_service = AuthenticationService(
        app.state.identity_store,
        app.state.token_service,
    )
    app.state.jwt_expire_minutes = (
        settings.jwt_access_token_expire_minutes if settings is not None else 30
    )

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
    app.include_router(auth_router)
    return app


app = create_app()
