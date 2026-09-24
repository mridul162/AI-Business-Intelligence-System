"""
PostgreSQL query-plan diagnostics.

This module provides developer-facing diagnostics for inspecting the
PostgreSQL execution plan of an already-built analytical query.

It does NOT:
- build analytical SQL,
- execute the analytical query through QueryExecutor,
- modify QueryPlan,
- replace QueryExecutor,
- automatically run EXPLAIN ANALYZE.

The diagnostic operates on the existing BuiltQuery produced by the
SQL Builder.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import Engine

from etl.analytics.sql.sql_models import BuiltQuery


class QueryPlanDiagnosticError(RuntimeError):
    """Raised when PostgreSQL query-plan diagnostics fail."""


class QueryPlanDiagnostics:
    """
    Inspect PostgreSQL's execution plan for a BuiltQuery.

    EXPLAIN is used by default and does not execute the underlying
    analytical query.

    EXPLAIN ANALYZE may be requested explicitly, but it executes the
    underlying query and should therefore only be used intentionally
    in controlled diagnostic environments.
    """

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def explain(
        self,
        built_query: BuiltQuery,
        *,
        analyze: bool = False,
    ) -> str:
        """
        Return PostgreSQL's textual execution plan.

        Args:
            built_query:
                The parameterized query produced by the SQL Builder.

            analyze:
                If False, execute EXPLAIN only.
                If True, execute EXPLAIN ANALYZE.

        Returns:
            PostgreSQL's textual query plan.

        Raises:
            QueryPlanDiagnosticError:
                If PostgreSQL cannot generate the requested plan.
        """
        statement, parameters = self._compile_query(built_query)

        explain_sql = (
            "EXPLAIN ANALYZE "
            if analyze
            else "EXPLAIN "
        ) + statement

        try:
            with self._engine.connect() as connection:
                result = connection.exec_driver_sql(
                    explain_sql,
                    parameters,
                )
                rows = result.fetchall()

        except Exception as exc:
            raise QueryPlanDiagnosticError(
                "Failed to generate PostgreSQL query plan."
            ) from exc

        return "\n".join(str(row[0]) for row in rows)

    @staticmethod
    def _compile_query(
        built_query: BuiltQuery,
    ) -> tuple[str, dict[str, Any]]:
        """
        Compile the SQLAlchemy Select using PostgreSQL's dialect.

        Values remain bound parameters and are not interpolated into
        the SQL string.
        """
        compiled = built_query.statement.compile(
            dialect=postgresql.dialect(),
        )

        return str(compiled), dict(compiled.params)