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
import logging
from typing import Optional

from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from etl.observability.metrics import metrics

# ADAPTER NOTE: I was given connection.py in isolation, without its
# package location in your project. This assumes it lives at
# `db/connection.py` (import path `db.connection`). If your real path
# differs (e.g. `app.db.connection`, `etl.db.connection`), this is the
# only line to change.
from database.connection import get_engine

from etl.analytics.sql.sql_models import BuiltQuery

from .errors import DatabaseConnectionError, QueryExecutionFailedError
from .execution_models import ExecutionResult

logger = logging.getLogger(__name__)


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

    def __init__(
        self,
        engine: Optional[Engine] = None,
        slow_query_threshold_ms: float = 500.0,
    ) -> None:

        if slow_query_threshold_ms <= 0:
            raise ValueError("slow_query_threshold_ms must be greater than 0.")
        
        self._engine = engine
        self._slow_query_threshold_ms = slow_query_threshold_ms

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

        metrics.increment("db_queries_total")

        start = time.perf_counter()

        try:
            with engine.connect() as connection:
                try:
                    result = connection.execute(built_query.statement)
                    columns = tuple(result.keys())
                    rows = tuple(dict(m) for m in result.mappings())
                except SQLAlchemyError as exc:
                    metrics.increment("db_queries_failed")
                    raise QueryExecutionFailedError(
                        "Query execution failed."
                    ) from exc

        except SQLAlchemyError as exc:
            metrics.increment("db_queries_failed")
            raise DatabaseConnectionError(
                "Failed to open a database connection."
            ) from exc

        duration = time.perf_counter() - start

        duration_ms = duration * 1000

        if duration_ms > self._slow_query_threshold_ms:
            logger.warning(
                "db_slow_query_detected "
                "duration_ms=%.2f "
                "threshold_ms=%.2f "
                "row_count=%d",
                duration_ms,
                self._slow_query_threshold_ms,
                len(rows),
            )

        metrics.increment("db_queries_successful")
        metrics.observe(
            "db_query_duration_ms",
            duration_ms,
        )
        metrics.add(
            "db_rows_returned",
            len(rows),
        )

        return ExecutionResult(
            columns=columns,
            rows=rows,
            row_count=len(rows),
            duration_seconds=duration,
        )