from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from sqlalchemy import bindparam, column, select, table

from etl.analytics.diagnostics.query_plan import (
    QueryPlanDiagnosticError,
    QueryPlanDiagnostics,
)
from etl.analytics.planner.query_plan import QueryPlan
from etl.analytics.sql.sql_models import BuiltQuery


def make_built_query() -> BuiltQuery:
    """Build a minimal BuiltQuery containing a bound parameter."""
    sales = table(
        "analytics.v_sales",
        column("net_sales"),
        column("customer_id"),
    )

    statement = select(sales.c.net_sales).where(
        sales.c.customer_id
        == bindparam(
            "customer_id",
            value="CUST001",
        )
    )

    plan = QueryPlan(
        metrics=("net_sales",),
        source_view="analytics.v_sales",
    )

    return BuiltQuery(
        statement=statement,
        plan=plan,
        metric_output_fields=("net_sales",),
        dimension_fields=(),
        time_bucket_alias=None,
    )


def make_mock_engine(
    rows: list[tuple[str, ...]],
) -> tuple[MagicMock, MagicMock, MagicMock]:
    """Create a mock engine/connection/result chain."""
    engine = MagicMock()
    connection = MagicMock()
    result = MagicMock()

    result.fetchall.return_value = rows
    connection.exec_driver_sql.return_value = result

    engine.connect.return_value.__enter__.return_value = connection

    return engine, connection, result


def test_compile_query_uses_postgresql_dialect() -> None:
    built_query = make_built_query()

    sql, parameters = QueryPlanDiagnostics._compile_query(
        built_query
    )

    assert "SELECT" in sql
    assert "analytics.v_sales" in sql
    assert "customer_id" in sql

    assert "customer_id" in parameters
    assert parameters["customer_id"] == "CUST001"

    # The value must remain a bound parameter.
    assert "CUST001" not in sql


def test_explain_uses_explain_without_analyze() -> None:
    built_query = make_built_query()

    engine, connection, _ = make_mock_engine(
        [
            ("Seq Scan on v_sales",),
            ("  Filter: (customer_id = 'CUST001')",),
        ]
    )

    diagnostics = QueryPlanDiagnostics(engine)

    plan = diagnostics.explain(built_query)

    assert plan == (
        "Seq Scan on v_sales\n"
        "  Filter: (customer_id = 'CUST001')"
    )

    connection.exec_driver_sql.assert_called_once()

    executed_sql = connection.exec_driver_sql.call_args.args[0]

    assert "EXPLAIN " in executed_sql
    assert "EXPLAIN ANALYZE" not in executed_sql


def test_explain_analyze_is_only_used_when_explicitly_requested() -> None:
    built_query = make_built_query()

    engine, connection, _ = make_mock_engine(
        [
            ("Seq Scan on v_sales",),
            ("Planning Time: 0.100 ms",),
            ("Execution Time: 0.200 ms",),
        ]
    )

    diagnostics = QueryPlanDiagnostics(engine)

    diagnostics.explain(
        built_query,
        analyze=True,
    )

    connection.exec_driver_sql.assert_called_once()

    executed_sql = connection.exec_driver_sql.call_args.args[0]

    assert "EXPLAIN ANALYZE" in executed_sql


def test_explain_passes_compiled_parameters_separately() -> None:
    built_query = make_built_query()

    engine, connection, _ = make_mock_engine(
        [
            ("Index Scan using idx_customer_id",),
        ]
    )

    diagnostics = QueryPlanDiagnostics(engine)

    diagnostics.explain(built_query)

    connection.exec_driver_sql.assert_called_once()

    call_args = connection.exec_driver_sql.call_args

    assert len(call_args.args) == 2

    executed_sql = call_args.args[0]
    parameters = call_args.args[1]

    assert "EXPLAIN " in executed_sql
    assert parameters["customer_id"] == "CUST001"


def test_explain_returns_all_plan_rows() -> None:
    built_query = make_built_query()

    engine, connection, _ = make_mock_engine(
        [
            ("Aggregate",),
            ("  -> Seq Scan on v_sales",),
            ("Planning Time: 0.120 ms",),
        ]
    )

    diagnostics = QueryPlanDiagnostics(engine)

    plan = diagnostics.explain(built_query)

    assert plan.splitlines() == [
        "Aggregate",
        "  -> Seq Scan on v_sales",
        "Planning Time: 0.120 ms",
    ]


def test_explain_wraps_database_errors() -> None:
    built_query = make_built_query()

    engine = MagicMock()
    connection = MagicMock()

    connection.exec_driver_sql.side_effect = RuntimeError(
        "database connection failed"
    )

    engine.connect.return_value.__enter__.return_value = connection

    diagnostics = QueryPlanDiagnostics(engine)

    with pytest.raises(QueryPlanDiagnosticError) as exc_info:
        diagnostics.explain(built_query)

    assert (
        "Failed to generate PostgreSQL query plan."
        in str(exc_info.value)
    )

    assert isinstance(
        exc_info.value.__cause__,
        RuntimeError,
    )


def test_explain_does_not_use_analyze_by_default() -> None:
    built_query = make_built_query()

    engine, connection, _ = make_mock_engine(
        [
            ("Seq Scan on v_sales",),
        ]
    )

    diagnostics = QueryPlanDiagnostics(engine)

    diagnostics.explain(built_query)

    connection.exec_driver_sql.assert_called_once()

    executed_sql = connection.exec_driver_sql.call_args.args[0]

    assert executed_sql.startswith("EXPLAIN ")
    assert not executed_sql.startswith("EXPLAIN ANALYZE ")