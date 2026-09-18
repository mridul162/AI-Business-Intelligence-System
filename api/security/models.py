from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from etl.analytics.context.request_context import TenantScope


class Role(StrEnum):
	ADMIN = "admin"
	ANALYST = "analyst"
	VIEWER = "viewer"


@dataclass(frozen=True)
class Tenant:
	id: UUID
	name: str
	is_active: bool = True


@dataclass(frozen=True)
class User:
	id: UUID
	email: str
	password_hash: str
	tenant_id: UUID
	role: Role
	is_active: bool = True


class IdentityStore(Protocol):
	def get_user_by_email(self, email: str) -> User | None: ...

	def get_user(self, user_id: UUID) -> User | None: ...

	def get_tenant(self, tenant_id: UUID) -> Tenant | None: ...


class InMemoryIdentityStore:
	"""Small deterministic store for tests and local development."""

	def __init__(
		self,
		*,
		users: tuple[User, ...] = (),
		tenants: tuple[Tenant, ...] = (),
	) -> None:
		self.users = {user.id: user for user in users}
		self.tenants = {tenant.id: tenant for tenant in tenants}

	def get_user_by_email(self, email: str) -> User | None:
		normalized = email.strip().casefold()
		return next(
			(user for user in self.users.values() if user.email.casefold() == normalized),
			None,
		)

	def get_user(self, user_id: UUID) -> User | None:
		return self.users.get(user_id)

	def get_tenant(self, tenant_id: UUID) -> Tenant | None:
		return self.tenants.get(tenant_id)
