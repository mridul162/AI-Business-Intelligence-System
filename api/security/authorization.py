from __future__ import annotations

from collections.abc import Callable
from fastapi import Depends, HTTPException, status

from .errors import AuthorizationError
from .dependencies import require_authenticated_user
from .models import Role, User


def require_role(required_role: Role) -> Callable[[User], User]:
	"""Return a dependency that permits only the requested role."""

	def dependency(user: User = Depends(require_authenticated_user)) -> User:
		if user.role is not required_role:
			raise HTTPException(
				status_code=status.HTTP_403_FORBIDDEN,
				detail="Insufficient permissions.",
			)
		return user

	return dependency
