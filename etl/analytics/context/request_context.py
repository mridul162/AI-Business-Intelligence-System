from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class TenantScope:
    """Trusted tenant boundary supplied by authentication context."""

    tenant_id: UUID


@dataclass(frozen=True)
class RequestContext:
    """Context associated with a single application request."""

    request_id: UUID
    user_id: UUID | None = None
    tenant_id: UUID | None = None
    role: str | None = None

    @property
    def is_authenticated(self) -> bool:
        return self.user_id is not None and self.tenant_id is not None


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


def set_authenticated_identity(
    *,
    user_id: UUID,
    tenant_id: UUID,
    role: str,
) -> None:
    """Attach verified identity claims to the current request context."""
    current = get_request_context()
    if current is None:
        return
    _request_context.set(
        RequestContext(
            request_id=current.request_id,
            user_id=user_id,
            tenant_id=tenant_id,
            role=role,
        )
    )