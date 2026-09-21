from __future__ import annotations

from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine
from sqlalchemy.orm import Session

from etl.data_quality.checks.schema import table_exists_check, columns_exist_check
from etl.data_quality.models import DataQualityCheck, DataQualityResult
from etl.data_quality.registry import DataQualityRegistry


def _build_sqlite_session() -> Session:
    engine = create_engine("sqlite://")
    metadata = MetaData()

    Table(
        "orders",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("customer_id", Integer),
        Column("amount", Integer),
    )
    Table(
        "customers",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("email", String),
    )

    metadata.create_all(engine)
    return Session(engine)


def test_table_exists_check_passes_for_real_table() -> None:
    with _build_sqlite_session() as session:
        result = table_exists_check(session, "orders")

    assert result.status == "PASS"
    assert result.check_name == "table_exists:orders"
    assert result.affected_rows == 0


def test_columns_exist_check_detects_missing_column() -> None:
    with _build_sqlite_session() as session:
        result = columns_exist_check(session, "orders", ["id", "customer_id", "missing_col"])

    assert result.status == "FAIL"
    assert result.severity == "ERROR"
    assert result.affected_rows == 1
    assert "missing_col" in result.message


def test_registry_runs_checks_and_aggregates_status() -> None:
    registry = DataQualityRegistry()
    registry.register(
        DataQualityCheck(
            name="sample_pass",
            func=lambda session: DataQualityResult(
                check_name="sample_pass",
                status="PASS",
                severity="INFO",
                message="ok",
            ),
        )
    )
    registry.register(
        DataQualityCheck(
            name="sample_warning",
            func=lambda session: DataQualityResult(
                check_name="sample_warning",
                status="WARNING",
                severity="WARNING",
                affected_rows=2,
                message="partial issue",
            ),
        )
    )

    with _build_sqlite_session() as session:
        report = registry.run(session)

    assert report.status == "WARNING"
    assert len(report.checks) == 2
    assert report.summary["pass_count"] == 1
    assert report.summary["warning_count"] == 1
