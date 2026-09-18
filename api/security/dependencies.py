from __future__ import annotations

from uuid import UUID

from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from etl.analytics.context.request_context import set_authenticated_identity

from .authentication import TokenService
from .errors import TokenError
from .models import IdentityStore, User


bearer_scheme = HTTPBearer(auto_error=False)


def _unauthorized(detail: str = "Authentication required.") -> HTTPException:
	return HTTPException(
		status_code=status.HTTP_401_UNAUTHORIZED,
		detail=detail,
		headers={"WWW-Authenticate": "Bearer"},
	)


def get_current_user(
	request: Request,
	credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
) -> User | None:
	if not request.app.state.auth_enabled:
		return None
	if credentials is None or credentials.scheme.lower() != "bearer":
		raise _unauthorized()

	token_service: TokenService = request.app.state.token_service
	try:
		claims = token_service.decode_access_token(credentials.credentials)
		user_id = UUID(str(claims["sub"]))
		tenant_id = UUID(str(claims["tenant_id"]))
	except (TokenError, ValueError, KeyError, TypeError) as exc:
		raise _unauthorized("Invalid access token.") from exc

	store: IdentityStore = request.app.state.identity_store
	user = store.get_user(user_id)
	tenant = store.get_tenant(tenant_id)
	if (
		user is None
		or not user.is_active
		or user.tenant_id != tenant_id
		or tenant is None
		or not tenant.is_active
	):
		raise _unauthorized("Invalid access token.")

	set_authenticated_identity(
		user_id=user.id,
		tenant_id=user.tenant_id,
		role=user.role.value,
	)
	return user


def require_authenticated_user(
	request: Request,
	user: User | None = Depends(get_current_user),
) -> User:
	if not request.app.state.auth_enabled:
		return None  # type: ignore[return-value]
	if user is None:
		raise _unauthorized()
	return user
