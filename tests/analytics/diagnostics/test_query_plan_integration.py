"""
Integration tests for PostgreSQL query-plan diagnostics.

These tests use the real PostgreSQL test database and the real SQL
Builder. They verify that a BuiltQuery produced by the analytics
pipeline can be passed to QueryPlanDiagnostics and successfully
inspected with PostgreSQL EXPLAIN.

EXPLAIN is used by default and therefore does not execute the
underlying analytical query.

Requires a reachable PostgreSQL instance. The tests are skipped when
the configured integration database is unavailable.
"""

from __future__ import annotations

from functools import partial

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from etl.analytics.diagnostics.query_plan import QueryPlanDiagnostics
from etl.analytics.metrics.registry import get_metric
from etl.analytics.planner.query_plan import QueryPlan
from etl.analytics.sql.sql_builder import build_query
from etl.analytics.planner.query_plan import PlanFilter


# --------------------------------------------------------------------
# Test database connection
# --------------------------------------------------------------------

TEST_DB_URL = (
    "postgresql+psycopg2://"
    "aibi_test:aibi_test_pw@localhost:5432/aibi_test_db"
)


@pytest.fixture(scope="module")
def postgres_engine() -> Engine: # pyright: ignore[reportInvalidTypeForm]
    engine = create_engine(TEST_DB_URL, future=True)

    try:
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
    except Exception as exc:  # pragma: no cover - environment-dependent
        pytest.skip(
            f"Integration test Postgres not reachable: {exc}"
        )

    yield engine # pyright: ignore[reportReturnType]
    engine.dispose()


# --------------------------------------------------------------------
# Real BuiltQuery
# --------------------------------------------------------------------


@pytest.fixture
def built_query():
    """
    Build a real BuiltQuery using the production SQL Builder.
    """
    plan = QueryPlan(
        metrics=("gross_sales",),
        source_view="analytics.v_sales",
    )

    return build_query(
        plan,
        get_metric=get_metric,
        time_column_by_view={
            "analytics.v_sales": "sale_date",
            "analytics.v_expenses": "expense_date",
            "analytics.v_cash_transactions": "transaction_date",
        },
    )


# --------------------------------------------------------------------
# EXPLAIN
# --------------------------------------------------------------------


def test_explain_real_built_query(
    postgres_engine: Engine,
    built_query,
) -> None:
    diagnostics = QueryPlanDiagnostics(postgres_engine)

    plan = diagnostics.explain(built_query)

    assert plan
    assert isinstance(plan, str)

    # PostgreSQL's textual EXPLAIN output should contain a scan node.
    assert any(
        keyword in plan
        for keyword in (
            "Seq Scan",
            "Index Scan",
            "Index Only Scan",
            "Bitmap Heap Scan",
            "Bitmap Index Scan",
        )
    )


def test_explain_real_query_with_bound_parameter(
    postgres_engine: Engine,
) -> None:
    plan = QueryPlan(
        metrics=("gross_sales",),
        source_view="analytics.v_sales",
        filters=(
            PlanFilter(
                field="product_category",
                operator="eq",
                value="Nuts",
            ),
        ),
    )

    built_query = build_query(
        plan,
        get_metric=get_metric,
        time_column_by_view={
            "analytics.v_sales": "sale_date",
            "analytics.v_expenses": "expense_date",
            "analytics.v_cash_transactions": "transaction_date",
        },
    )

    diagnostics = QueryPlanDiagnostics(postgres_engine)

    result = diagnostics.explain(built_query)

    assert result
    assert isinstance(result, str)