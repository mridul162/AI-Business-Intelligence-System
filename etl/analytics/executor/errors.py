"""
Exceptions raised while executing a BuiltQuery.

Only sqlalchemy.exc.SQLAlchemyError is ever translated into these --
anything else (a genuine bug in our code, a bad argument type, etc.)
is left to propagate as-is. See executor.py.
"""

from __future__ import annotations


class QueryExecutorError(Exception):
    """Base class for all query-executor errors."""


class DatabaseConnectionError(QueryExecutorError):
    """Raised when engine.connect() itself fails (pool exhausted, DB
    unreachable, auth failure, etc.) -- before any statement ran."""


class QueryExecutionFailedError(QueryExecutorError):
    """Raised when a connection was obtained but executing or fetching
    built_query.statement failed (syntax error, missing table/column,
    constraint violation on a data-modifying statement, etc.)."""