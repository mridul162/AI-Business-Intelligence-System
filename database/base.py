"""
Declarative base + naming convention for the AI-BI PostgreSQL model.

A fixed naming convention is required so that Alembic autogenerate produces
stable, predictable constraint names (pk_..., fk_..., uq_..., ck_..., ix_...)
instead of Postgres' auto-generated ones, which differ across environments
and make diffing migrations unreliable.
"""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Shared declarative base for all core/staging/raw ORM models."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
