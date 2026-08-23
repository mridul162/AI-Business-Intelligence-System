"""Unit tests for etl.analytics.execution.executor.

A psycopg2-style connection/cursor is mocked — no real database needed.
CompiledQuery.sql uses %(name)s placeholders and params is a dict;
column names come from CompiledQuery.output_columns, not cursor
introspection, matching the real query/models.py contract.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from etl.analytics.execution.executor import (
    AnalyticalQueryExecutionError,
    AnalyticalQueryExecutor,
)
from etl.analytics.execution.models import QueryExecutionResult
from etl.analytics.query.models import CompiledQuery


def make_mock_connection(*, fetchall_rows: list[tuple]) -> MagicMock:
    """Build a mock connection whose cursor() context manager returns
    fetchall_rows as raw row tuples, psycopg2-style."""

    cursor = MagicMock()
    cursor.fetchall.return_value = fetchall_rows
    cursor.__enter__.return_value = cursor
    cursor.__exit__.return_value = False

    connection = MagicMock()
    connection.cursor.return_value = cursor
    return connection


class TestExecutorExecutesSql:
    def test_calls_cursor_execute_with_sql_and_params(self) -> None:
        connection = make_mock_connection(fetchall_rows=[])
        query = CompiledQuery(
            sql="SELECT 1 WHERE date >= %(start_date)s",
            params={"start_date": "2026-08-01"},
            output_columns=(),
        )

        AnalyticalQueryExecutor(connection).execute(query)

        cursor = connection.cursor.return_value
        cursor.execute.assert_called_once_with(query.sql, query.params)


class TestExecutorReturnsColumns:
    def test_returns_output_columns_from_query(self) -> None:
        connection = make_mock_connection(
            fetchall_rows=[("2026-08-01", Decimal("15990.00"))],
        )
        query = CompiledQuery(
            sql="SELECT business_date, total_sales FROM sales",
            params={},
            output_columns=("business_date", "total_sales"),
        )

        result = AnalyticalQueryExecutor(connection).execute(query)

        assert result.columns == ["business_date", "total_sales"]


class TestExecutorReturnsRowsAsDicts:
    def test_returns_serialized_row_dicts_zipped_with_output_columns(self) -> None:
        connection = make_mock_connection(
            fetchall_rows=[("2026-08-01", Decimal("15990.00"))],
        )
        query = CompiledQuery(
            sql="SELECT business_date, total_sales FROM sales",
            params={},
            output_columns=("business_date", "total_sales"),
        )

        result = AnalyticalQueryExecutor(connection).execute(query)

        assert result.rows == [
            {"business_date": "2026-08-01", "total_sales": 15990.0}
        ]


class TestExecutorCalculatesRowCount:
    def test_row_count_matches_number_of_rows(self) -> None:
        connection = make_mock_connection(
            fetchall_rows=[
                ("2026-08", Decimal("15990.00")),
                ("2026-09", Decimal("22000.00")),
            ],
        )
        query = CompiledQuery(
            sql="SELECT month, total_sales FROM sales",
            params={},
            output_columns=("month", "total_sales"),
        )

        result = AnalyticalQueryExecutor(connection).execute(query)

        assert result.row_count == 2


class TestExecutorHandlesEmptyResults:
    def test_empty_result_set_is_a_valid_result_not_an_error(self) -> None:
        connection = make_mock_connection(fetchall_rows=[])
        query = CompiledQuery(
            sql="SELECT total_sales FROM sales WHERE 1=0",
            params={},
            output_columns=("total_sales",),
        )

        result = AnalyticalQueryExecutor(connection).execute(query)

        assert result == QueryExecutionResult(
            columns=["total_sales"],
            rows=[],
            row_count=0,
        )


class TestExecutorErrorHandling:
    def test_propagates_raw_exception_by_default(self) -> None:
        connection = make_mock_connection(fetchall_rows=[])
        connection.cursor.return_value.execute.side_effect = RuntimeError(
            "db connection lost"
        )
        query = CompiledQuery(sql="SELECT 1", params={}, output_columns=())

        with pytest.raises(RuntimeError):
            AnalyticalQueryExecutor(connection).execute(query)

    def test_wraps_exception_when_raise_on_error_is_true(self) -> None:
        connection = make_mock_connection(fetchall_rows=[])
        connection.cursor.return_value.execute.side_effect = RuntimeError(
            "db connection lost"
        )
        query = CompiledQuery(sql="SELECT 1", params={}, output_columns=())

        executor = AnalyticalQueryExecutor(connection, raise_on_error=True)

        with pytest.raises(AnalyticalQueryExecutionError):
            executor.execute(query)
