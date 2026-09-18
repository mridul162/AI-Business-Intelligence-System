from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from .models import IdentityStore, Role, Tenant, User


class SqlAlchemyIdentityStore(IdentityStore):
    """Database-backed identity lookup used by the production composition root."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def get_user_by_email(self, email: str) -> User | None:
        with self._session_factory() as session:
            row = session.execute(
                text(
                    """
                    SELECT user_id, tenant_id, email, password_hash, role, is_active
                    FROM core.users
                    WHERE lower(email) = lower(:email)
                    """
                ),
                {"email": email.strip()},
            ).mappings().one_or_none()
        return _user_from_row(row)

    def get_user(self, user_id: UUID) -> User | None:
        with self._session_factory() as session:
            row = session.execute(
                text(
                    """
                    SELECT user_id, tenant_id, email, password_hash, role, is_active
                    FROM core.users
                    WHERE user_id = :user_id
                    """
                ),
                {"user_id": user_id},
            ).mappings().one_or_none()
        return _user_from_row(row)

    def get_tenant(self, tenant_id: UUID) -> Tenant | None:
        with self._session_factory() as session:
            row = session.execute(
                text(
                    """
                    SELECT tenant_id, name, is_active
                    FROM core.tenants
                    WHERE tenant_id = :tenant_id
                    """
                ),
                {"tenant_id": tenant_id},
            ).mappings().one_or_none()
        if row is None:
            return None
        return Tenant(
            id=UUID(str(row["tenant_id"])),
            name=str(row["name"]),
            is_active=bool(row["is_active"]),
        )


def _user_from_row(row) -> User | None:
    if row is None:
        return None
    return User(
        id=UUID(str(row["user_id"])),
        email=str(row["email"]),
        password_hash=str(row["password_hash"]),
        tenant_id=UUID(str(row["tenant_id"])),
        role=Role(str(row["role"])),
        is_active=bool(row["is_active"]),
    )