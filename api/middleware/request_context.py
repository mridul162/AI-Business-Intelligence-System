from __future__ import annotations

from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from etl.analytics.context.request_context import (
    RequestContext,
    reset_request_context,
    set_request_context,
)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach a request-scoped request ID to each HTTP request."""

    async def dispatch(
        self,
        request: Request,
        call_next,
    ) -> Response:
        request_id = uuid4()

        token = set_request_context(
            RequestContext(request_id=request_id)
        )

        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = str(request_id)
            return response
        finally:
            reset_request_context(token)