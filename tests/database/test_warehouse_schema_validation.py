from __future__ import annotations

import pytest
from sqlalchemy import create_engine

from database.connection import build_database_url

from etl.data_quality.checks.schema import (
    columns_exist_check,
    expected_column_types_check,
    required_not_null_columns_check,
    table_exists_check,
    view_exists_check,
)
from etl.data_quality.checks.warehouse_schema import (
    REQUIRED_ANALYTICAL_VIEWS,
    REQUIRED_WAREHOUSE_TABLES,
    warehouse_structure_check,
)

TEST_DB_URL = build_database_url()


@pytest.fixture(scope="module")
def postgres_engine():
    engine = create_engine(TEST_DB_URL, future=True)
    try:
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
    except Exception as exc:  # pragma: no cover - environment-dependent
        pytest.skip(f"Integration test Postgres not reachable: {exc}")
    yield engine
    engine.dispose()


def test_required_warehouse_tables_exist(postgres_engine):
    with postgres_engine.connect() as conn:
        for table_name in REQUIRED_WAREHOUSE_TABLES:
            result = table_exists_check(conn, table_name)
            assert result.status == "PASS", result.message


def test_required_analytical_views_exist(postgres_engine):
    with postgres_engine.connect() as conn:
        for view_name in REQUIRED_ANALYTICAL_VIEWS:
            result = view_exists_check(conn, view_name)
            assert result.status == "PASS", result.message


def test_required_columns_exist_for_core_fact_orders(postgres_engine):
    with postgres_engine.connect() as conn:
        result = columns_exist_check(
            conn,
            "core.fact_orders",
            ["order_key", "order_id", "date_key", "customer_key", "total_amount"],
        )
    assert result.status == "PASS"


def test_expected_types_match_live_schema(postgres_engine):
    with postgres_engine.connect() as conn:
        result = expected_column_types_check(
            conn,
            "core.fact_orders",
            {
                "order_key": "bigint",
                "order_id": "character varying",
                "date_key": "integer",
                "customer_key": "bigint",
                "total_amount": "numeric",
            },
        )
    assert result.status == "PASS"


def test_required_not_null_columns_match_live_schema(postgres_engine):
    with postgres_engine.connect() as conn:
        result = required_not_null_columns_check(
            conn,
            "core.fact_orders",
            ["order_key", "order_id", "date_key", "subtotal", "total_amount", "order_status", "ingestion_batch_id", "ingested_at"],
        )
    assert result.status == "PASS"


def test_warehouse_structure_check_passes_against_live_schema(postgres_engine):
    with postgres_engine.connect() as conn:
        report = warehouse_structure_check(conn)

    assert report.status == "PASS", report.message
