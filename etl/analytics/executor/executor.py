"""
Executes ONE already-built, already-validated SQL statement and
returns a predictable ExecutionResult.

This module does not build SQL, resolve metrics, parse natural
language, validate business rules, handle MultiQueryPlan, merge
results, or format answers -- see errors.py/execution_models.py for
the only two things it owns: translating DB errors and shaping the
result.
"""

from __future__ import annotations

import time
from typing import Optional

from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

# ADAPTER NOTE: I was given connection.py in isolation, without its
# package location in your project. This assumes it lives at
# `db/connection.py` (import path `db.connection`). If your real path
# differs (e.g. `app.db.connection`, `etl.db.connection`), this is the
# only line to change.
from database.connection import get_engine

from etl.analytics.sql.sql_models import BuiltQuery

from .errors import DatabaseConnectionError, QueryExecutionFailedError
from .execution_models import ExecutionResult


class QueryExecutor:
    """
    Executes a BuiltQuery using plain SQLAlchemy Core -- no ORM
    Session, no second Engine.

    Args:
        engine: an existing Engine to use (e.g. in tests). If omitted,
            the executor lazily resolves the application's real
            engine via db.connection.get_engine() on first use --
            it never constructs its own Engine.
    """

    def __init__(self, engine: Optional[Engine] = None) -> None:
        self._engine = engine

    def _resolve_engine(self) -> Engine:
        return self._engine if self._engine is not None else get_engine()

    def execute(self, built_query: BuiltQuery) -> ExecutionResult:
        """
        Run built_query.statement and return its results.

        Raises:
            DatabaseConnectionError: engine.connect() itself failed.
            QueryExecutionFailedError: a connection was obtained but
                executing or fetching the statement failed.
            Anything else (TypeError, AttributeError, a bug in our
                code, ...) is NOT caught here and propagates as-is.
        """
        engine = self._resolve_engine()

        start = time.perf_counter()
        try:
            with engine.connect() as connection:
                try:
                    result = connection.execute(built_query.statement)
                    columns = tuple(result.keys())
                    rows = tuple(dict(m) for m in result.mappings())
                except SQLAlchemyError as exc:
                    raise QueryExecutionFailedError(
                        "Query execution failed."
                    ) from exc
        except SQLAlchemyError as exc:
            raise DatabaseConnectionError(
                "Failed to open a database connection."
            ) from exc

        duration = time.perf_counter() - start

        return ExecutionResult(
            columns=columns,
            rows=rows,
            row_count=len(rows),
            duration_seconds=duration,
        )