"""
Integration test for the analytics pipeline: Milestone 5's
AnalyticsQueryOrchestrator wired to REAL components end-to-end,
against a REAL PostgreSQL database -- no mocks anywhere in this file.

    AnalyticalQueryRequest (fake request object, duck-typed)
            v
    etl.analytics.planner.query_planner.plan_query   (REAL)
            v
    QueryPlan / MultiQueryPlan
            v
    etl.analytics.sql.sql_builder.build_query         (REAL)
            v
    BuiltQuery
            v
    etl.analytics.executor.QueryExecutor              (REAL, against
            v                                          a real Postgres)
    ExecutionResult
            v
    etl.analytics.merger.ResultMerger                  (REAL)
            v
    AnalyticalResult

Unit tests elsewhere already prove each component and the
orchestrator's coordination logic in isolation with fakes. This file
proves the CONTRACTS between the real components actually line up:
that plan_query's output satisfies what build_query expects, that
build_query's BuiltQuery satisfies what QueryExecutor and ResultMerger
expect, and that real driver values (Decimal, date) survive the whole
round trip.

Requires a reachable PostgreSQL instance. Skips (not fails) if one
isn't configured -- see the `postgres_engine` fixture.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from functools import partial
from typing import Any, Optional

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from etl.analytics.executor import QueryExecutor
from etl.analytics.merger import ResultMerger
from etl.analytics.metrics.registry import get_metric
from etl.analytics.orchestration import AnalyticalResult, AnalyticsQueryOrchestrator
from etl.analytics.planner.query_plan import MergeStrategy
from etl.analytics.planner.query_planner import plan_query
from etl.analytics.sql.sql_builder import build_query

# --------------------------------------------------------------------
# Test database connection
# --------------------------------------------------------------------

TEST_DB_URL = os.environ.get(
    "AIBI_INTEGRATION_TEST_DB_URL",
    "postgresql+psycopg2://aibi_test:aibi_test_pw@localhost:5432/aibi_test_db",
)


@pytest.fixture(scope="module")
def postgres_engine() -> Engine: # type: ignore
    engine = create_engine(TEST_DB_URL, future=True)
    try:
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
    except Exception as exc:  # pragma: no cover - environment-dependent
        pytest.skip(f"Integration test Postgres not reachable: {exc}")
    yield engine # type: ignore
    engine.dispose()


# --------------------------------------------------------------------
# Request stand-in
# --------------------------------------------------------------------
# plan_query() only ever reads these attributes via getattr (see
# query_planner.py) -- this is the same duck-typed shape used in
# test_query_planner.py, standing in for whatever the real semantic
# resolver's AnalyticalQueryRequest looks like.


@dataclass
class FakeAnalyticalQueryRequest:
    metrics: tuple[str, ...]
    dimensions: tuple[str, ...] = ()
    filters: tuple[Any, ...] = ()
    time_range: Any = None
    time_grain: Optional[str] = None
    sort_by: Optional[str] = None
    sort_order: Optional[str] = None
    limit: Optional[int] = None
    comparison: bool = False


# --------------------------------------------------------------------
# Real-component wiring, matching how application code would assemble
# this (see analytics_orchestrator.py's docstring for the intended
# functools.partial pattern).
# --------------------------------------------------------------------


@pytest.fixture
def orchestrator(postgres_engine: Engine) -> AnalyticsQueryOrchestrator:
    real_planner = partial(plan_query, resolve_metric=get_metric)
    real_builder = partial(
        build_query,
        get_metric=get_metric,
        time_column_by_view={
            "analytics.v_sales": "sale_date",
            "analytics.v_expenses": "expense_date",
            "analytics.v_cash_transactions": "transaction_date",
        },
    )
    real_executor = QueryExecutor(engine=postgres_engine)
    real_merger = ResultMerger()

    return AnalyticsQueryOrchestrator(
        planner=real_planner,
        builder=real_builder,
        executor=real_executor,
        merger=real_merger,
    )


# --------------------------------------------------------------------
# Single QueryPlan, full real stack
# --------------------------------------------------------------------


def test_single_metric_grouped_by_dimension(orchestrator):
    request = FakeAnalyticalQueryRequest(
        metrics=("gross_sales",),
        dimensions=("product_category",),
    )

    result = orchestrator.execute(request)

    assert isinstance(result, AnalyticalResult)
    assert result.merge_strategy is MergeStrategy.NONE
    assert set(result.columns) == {"product_category", "gross_sales"}

    by_category = {r["product_category"]: r["gross_sales"] for r in result.rows}
    assert by_category["Nuts"] == Decimal("1500.00")
    assert by_category["Snacks"] == Decimal("1650.25")
    assert all(isinstance(v, Decimal) for v in by_category.values())


def test_single_metric_by_month_preserves_dates(orchestrator):
    request = FakeAnalyticalQueryRequest(metrics=("gross_sales",), time_grain="monthly")

    result = orchestrator.execute(request)

    assert result.merge_strategy is MergeStrategy.NONE
    assert "period" in result.columns
    for row in result.rows:
        assert isinstance(row["period"], date)
        assert isinstance(row["gross_sales"], Decimal)
    total = sum((row["gross_sales"] for row in result.rows), Decimal("0"))
    assert total == Decimal("3150.25")  # all four seeded sales rows


# --------------------------------------------------------------------
# MultiQueryPlan: SPLIT_METRICS (same view, conflicting fixed filters)
# --------------------------------------------------------------------


def test_split_metrics_cash_in_and_cash_out_real_stack(orchestrator):
    request = FakeAnalyticalQueryRequest(
        metrics=("cash_in", "cash_out"),
        time_grain="monthly",
    )

    result = orchestrator.execute(request)

    assert result.merge_strategy is MergeStrategy.SPLIT_METRICS
    assert set(result.columns) == {"period", "cash_in", "cash_out"}

    by_month = {row["period"].month: row for row in result.rows}

    # January: both cash_in and cash_out rows exist.
    assert by_month[1]["cash_in"] == Decimal("10000.00")
    assert by_month[1]["cash_out"] == Decimal("7000.00")

    # February: cash_in exists, cash_out has NO row at all for Feb ->
    # the merger fills 0, not None -- and this is coming from a real
    # executed SQL query with genuinely no matching row, not a fake.
    assert by_month[2]["cash_in"] == Decimal("12000.00")
    assert by_month[2]["cash_out"] == 0

    # March: the reverse -- only cash_out has data.
    assert by_month[3]["cash_out"] == Decimal("5000.00")
    assert by_month[3]["cash_in"] == 0


# --------------------------------------------------------------------
# MultiQueryPlan: COMPARE_METRICS (different views, explicit comparison)
# --------------------------------------------------------------------


def test_compare_metrics_sales_vs_expenses_real_stack(orchestrator):
    request = FakeAnalyticalQueryRequest(
        metrics=("gross_sales", "total_expenses"),
        time_grain="monthly",
        comparison=True,
    )

    result = orchestrator.execute(request)

    assert result.merge_strategy is MergeStrategy.COMPARE_METRICS
    assert set(result.columns) == {"period", "gross_sales", "total_expenses"}

    by_month = {row["period"].month: row for row in result.rows}
    assert by_month[1]["gross_sales"] == Decimal("1750.25")
    assert by_month[1]["total_expenses"] == Decimal("360.00")
    assert by_month[2]["gross_sales"] == Decimal("1400.00")
    assert by_month[2]["total_expenses"] == Decimal("300.00")


# --------------------------------------------------------------------
# MultiQueryPlan: SIDE_BY_SIDE (different views, no comparison framing)
# --------------------------------------------------------------------


def test_side_by_side_sales_and_expenses_scalar_real_stack(orchestrator):
    request = FakeAnalyticalQueryRequest(metrics=("gross_sales", "total_expenses"))

    result = orchestrator.execute(request)

    assert result.merge_strategy is MergeStrategy.SIDE_BY_SIDE
    assert result.row_count == 1
    row = result.rows[0]
    assert row["gross_sales"] == Decimal("3150.25")
    assert row["total_expenses"] == Decimal("660.00")


# --------------------------------------------------------------------
# Real filter + real bound parameter through the whole stack
# --------------------------------------------------------------------


def test_user_filter_is_applied_through_real_stack(orchestrator):
    from etl.analytics.planner.query_plan import PlanFilter

    request = FakeAnalyticalQueryRequest(
        metrics=("gross_sales",),
        dimensions=("product_category",),
        filters=(PlanFilter(field="product_category", operator="eq", value="Nuts"),),
    )

    result = orchestrator.execute(request)

    assert len(result.rows) == 1
    assert result.rows[0]["product_category"] == "Nuts"
    assert result.rows[0]["gross_sales"] == Decimal("1500.00")