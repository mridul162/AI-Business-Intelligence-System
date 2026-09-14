"""
Database connection and session management for the AI-BI platform.

Database configuration is provided by the centralized analytics Settings
object so the same configuration source is used across the application,
CLI tools, tests, and migrations.
"""

from __future__ import annotations

from contextlib import contextmanager
from functools import lru_cache
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import URL, Engine
from sqlalchemy.orm import Session, sessionmaker

from etl.analytics.config import Settings, get_settings


def build_database_url(settings: Settings | None = None) -> URL:
    """
    Build the PostgreSQL database URL from application settings.

    Args:
        settings: Optional Settings instance. When omitted, the cached
            application settings are used.

    Returns:
        SQLAlchemy database URL.
    """
    settings = settings or get_settings()

    return URL.create(
        drivername="postgresql+psycopg2",
        username=settings.db_user,
        password=settings.db_password,
        host=settings.db_host,
        port=settings.db_port,
        database=settings.db_name,
    )


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """
    Return the cached SQLAlchemy engine.

    Database configuration comes exclusively from Settings.
    """
    settings = get_settings()

    return create_engine(
        build_database_url(settings),
        echo=settings.db_echo,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_pre_ping=True,
        future=True,
    )


@lru_cache(maxsize=1)
def get_sessionmaker() -> sessionmaker[Session]:
    """Return the cached SQLAlchemy session factory."""
    return sessionmaker(
        bind=get_engine(),
        autoflush=False,
        expire_on_commit=False,
    )


@contextmanager
def session_scope() -> Iterator[Session]:
    """
    Provide a transactional SQLAlchemy session.

    Commits on successful completion, rolls back on exceptions,
    and always closes the session.
    """
    session = get_sessionmaker()()

    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()