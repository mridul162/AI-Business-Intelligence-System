"""
Database connection and session management for the AI-BI platform.

Configuration is read from environment variables so the same code works
across local development, CI, and production without code changes.

Required env vars (see .env.example):
    AIBI_DB_HOST
    AIBI_DB_PORT
    AIBI_DB_NAME
    AIBI_DB_USER
    AIBI_DB_PASSWORD

Optional:
    AIBI_DB_ECHO           ("true"/"false", default "false")
    AIBI_DB_POOL_SIZE       (default 5)
    AIBI_DB_MAX_OVERFLOW    (default 10)
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from functools import lru_cache
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import URL, Engine
from sqlalchemy.orm import Session, sessionmaker


def _env_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


def build_database_url() -> URL:
    """Build a SQLAlchemy URL from environment variables.

    Using URL.create() (rather than an f-string) avoids issues with
    special characters in passwords and keeps the driver name centralized.
    """
    return URL.create(
        drivername="postgresql+psycopg2",
        username=os.environ["AIBI_DB_USER"],
        password=os.environ.get("AIBI_DB_PASSWORD", ""),
        host=os.environ.get("AIBI_DB_HOST", "localhost"),
        port=int(os.environ.get("AIBI_DB_PORT", "5432")),
        database=os.environ["AIBI_DB_NAME"],
    )


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Return a process-wide singleton engine.

    Cached with lru_cache so repeated calls (e.g. from multiple modules)
    reuse the same connection pool instead of opening a new one each time.
    """
    return create_engine(
        build_database_url(),
        echo=_env_bool("AIBI_DB_ECHO", False),
        pool_size=int(os.environ.get("AIBI_DB_POOL_SIZE", "5")),
        max_overflow=int(os.environ.get("AIBI_DB_MAX_OVERFLOW", "10")),
        pool_pre_ping=True,  # avoids stale-connection errors after idle periods
        future=True,
    )


@lru_cache(maxsize=1)
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


@contextmanager
def session_scope() -> Iterator[Session]:
    """Provide a transactional scope around a series of operations.

    Usage:
        with session_scope() as session:
            session.execute(...)

    Commits on clean exit, rolls back and re-raises on any exception.
    This is the pattern ingestion/loading jobs should use rather than
    managing commit/rollback manually at every call site.
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
