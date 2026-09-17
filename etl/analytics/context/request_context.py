from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class RequestContext:
    """Context associated with a single application request."""

    request_id: UUID


_request_context: ContextVar[RequestContext | None] = ContextVar(
    "request_context",
    default=None,
)


def set_request_context(context: RequestContext):
    """Set the current request context."""
    return _request_context.set(context)


def reset_request_context(token) -> None:
    """Reset the current request context."""
    _request_context.reset(token)


def get_request_context() -> RequestContext | None:
    """Return the current request context, if one exists."""

    return _request_context.get()