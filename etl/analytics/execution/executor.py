"""
Execute validated analytical SQL queries.

NOTE ON DB API: CompiledQuery.sql uses psycopg2-style named
placeholders (`%(name)s`), not SQLAlchemy's `:name` bind-param
syntax. That means this executor talks to a raw psycopg2-style
connection/cursor (cursor.execute(sql, params_dict)) — it does
NOT go through sqlalchemy.text(), since text() only understands
`:name` placeholders and would silently fail to bind `%(name)s`
params. If your actual DB layer is a SQLAlchemy Connection/Session,
grab its raw DBAPI cursor first (e.g. `session.connection().connection.cursor()`)
and pass that in here.
"""

from __future__ import annotations

from typing import Any, Protocol

from etl.analytics.execution.models import (
    QueryExecutionResult,
)
from etl.analytics.execution.serializer import (
    serialize_rows,
)
from etl.analytics.query.models import CompiledQuery


class AnalyticalQueryExecutionError(Exception):
    """Raised when an analytical query cannot be executed.

    Not raised by default — see the `raise_on_error` flag on
    AnalyticalQueryExecutor. Left here so callers (e.g. a future
    FastAPI layer) can opt in without you having to hunt for it later.
    """


class Cursor(Protocol):
    """The minimal DBAPI cursor surface this executor relies on.

    Matches psycopg2's cursor: execute(sql, params) with %(name)s
    placeholders, then fetchall() returning a list of row tuples in
    the same column order as the SELECT.
    """

    def execute(self, sql: str, params: dict[str, Any]) -> None: ...

    def fetchall(self) -> list[tuple[Any, ...]]: ...

    def __enter__(self) -> "Cursor": ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: Any,
    ) -> bool | None: ...


class ConnectionLike(Protocol):
    """Minimal surface for something that can hand out a cursor,
    used as a context manager (as psycopg2 connections/cursors are)."""

    def cursor(self) -> Cursor: ...


class AnalyticalQueryExecutor:
    """Execute compiled analytical queries.

    Deliberately boring: it does not parse, resolve, or build SQL.
    It takes an already-validated CompiledQuery and runs it as a
    parameterized statement. Never concatenates user input into SQL.
    """

    def __init__(
        self,
        connection: ConnectionLike,
        *,
        raise_on_error: bool = False,
    ) -> None:
        self.connection = connection
        self.raise_on_error = raise_on_error

    def execute(
        self,
        query: CompiledQuery,
    ) -> QueryExecutionResult:
        """Execute a compiled analytical query and return a structured result.

        An empty result set is a valid, successful outcome (row_count=0),
        not an error. Only a failed execution is an error.
        """

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(query.sql, query.params)
                raw_result_rows = cursor.fetchall()
        except Exception as exc:
            if self.raise_on_error:
                raise AnalyticalQueryExecutionError(
                    "Failed to execute analytical query."
                ) from exc
            raise

        columns = list(query.output_columns)

        raw_rows = [
            dict(zip(columns, row))
            for row in raw_result_rows
        ]

        rows = serialize_rows(raw_rows)

        return QueryExecutionResult(
            columns=columns,
            rows=rows,
            row_count=len(rows),
        )
