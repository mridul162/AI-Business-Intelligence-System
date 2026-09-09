from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from sqlalchemy import Column, Date, Integer, MetaData, Numeric, String, Table, create_engine, select, text
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from etl.analytics.executor import (
    DatabaseConnectionError,
    ExecutionResult,
    QueryExecutionFailedError,
    QueryExecutor,
)
from etl.analytics.planner.query_plan import QueryPlan
from etl.analytics.sql.sql_models import BuiltQuery


@pytest.fixture
def sqlite_engine():
    engine = create_engine("sqlite://")
    metadata = MetaData()
    sales = Table(
        "sales",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("customer_name", String),
        Column("amount", Numeric(10, 2)),
        Column("sale_date", Date),
    )
    metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(
            sales.insert(),
            [
                {
                    "id": 1,
                    "customer_name": "Alice",
                    "amount": Decimal("100.50"),
                    "sale_date": date(2026, 1, 15),
                },
                {
                    "id": 2,
                    "customer_name": "Bob",
                    "amount": Decimal("250.00"),
                    "sale_date": date(2026, 2, 1),
                },
                {
                    "id": 3,
                    "customer_name": None,
                    "amount": Decimal("0.00"),
                    "sale_date": date(2026, 2, 2),
                },
            ],
        )
    yield engine, sales
    engine.dispose()


def _built_query(statement) -> BuiltQuery:
    """Wrap a plain Select in a real BuiltQuery, using a real QueryPlan."""
    plan = QueryPlan(source_view="sales", metrics=("amount",))
    return BuiltQuery(
        statement=statement,
        plan=plan,
        metric_output_fields=("amount",),
        dimension_fields=(),
        time_bucket_alias=None,
    )


# --------------------------------------------------------------------
# Successful execution
# --------------------------------------------------------------------


def test_successful_execution_multiple_rows(sqlite_engine):
    engine, sales = sqlite_engine
    stmt = select(sales.c.customer_name, sales.c.amount).order_by(sales.c.id)
    built_query = _built_query(stmt)

    executor = QueryExecutor(engine=engine)
    result = executor.execute(built_query)

    assert isinstance(result, ExecutionResult)
    assert result.columns == ("customer_name", "amount")
    assert result.row_count == 3
    assert len(result.rows) == 3


def test_correct_column_names(sqlite_engine):
    engine, sales = sqlite_engine
    stmt = select(sales.c.id, sales.c.sale_date)
    built_query = _built_query(stmt)

    result = QueryExecutor(engine=engine).execute(built_query)

    assert result.columns == ("id", "sale_date")


def test_rows_are_plain_dicts_keyed_by_column(sqlite_engine):
    engine, sales = sqlite_engine
    stmt = select(sales.c.customer_name, sales.c.amount).where(sales.c.id == 1)
    built_query = _built_query(stmt)

    result = QueryExecutor(engine=engine).execute(built_query)

    assert result.rows == ({"customer_name": "Alice", "amount": Decimal("100.50")},)
    assert all(type(r) is dict for r in result.rows)


def test_native_value_preservation(sqlite_engine):
    engine, sales = sqlite_engine
    stmt = select(sales.c.amount, sales.c.sale_date, sales.c.customer_name).where(
        sales.c.id == 1
    )
    built_query = _built_query(stmt)

    result = QueryExecutor(engine=engine).execute(built_query)
    row = result.rows[0]

    assert isinstance(row["amount"], Decimal)
    assert row["amount"] == Decimal("100.50")
    assert isinstance(row["sale_date"], date)
    assert row["sale_date"] == date(2026, 1, 15)
    assert isinstance(row["customer_name"], str)


def test_null_value_preserved_as_none(sqlite_engine):
    engine, sales = sqlite_engine
    stmt = select(sales.c.customer_name).where(sales.c.id == 3)
    built_query = _built_query(stmt)

    result = QueryExecutor(engine=engine).execute(built_query)

    assert result.rows[0]["customer_name"] is None


def test_row_count_matches_rows_length(sqlite_engine):
    engine, sales = sqlite_engine
    stmt = select(sales.c.id)
    built_query = _built_query(stmt)

    result = QueryExecutor(engine=engine).execute(built_query)

    assert result.row_count == len(result.rows) == 3


def test_duration_is_non_negative_float(sqlite_engine):
    engine, sales = sqlite_engine
    stmt = select(sales.c.id)
    built_query = _built_query(stmt)

    result = QueryExecutor(engine=engine).execute(built_query)

    assert isinstance(result.duration_seconds, float)
    assert result.duration_seconds >= 0.0


# --------------------------------------------------------------------
# Empty result -> still successful
# --------------------------------------------------------------------


def test_empty_result_is_successful(sqlite_engine):
    engine, sales = sqlite_engine
    stmt = select(sales.c.id).where(sales.c.id == 999)
    built_query = _built_query(stmt)

    result = QueryExecutor(engine=engine).execute(built_query)

    assert result.rows == ()
    assert result.row_count == 0
    assert result.columns == ("id",)  # keys() available even with 0 rows


# --------------------------------------------------------------------
# Error translation
# --------------------------------------------------------------------


def test_connection_failure_becomes_database_connection_error():
    fake_engine = MagicMock()
    fake_engine.connect.side_effect = OperationalError(
        "connect failed", None, None
    )
    built_query = _built_query(select(text("1")))

    with pytest.raises(DatabaseConnectionError) as excinfo:
        QueryExecutor(engine=fake_engine).execute(built_query)

    assert isinstance(excinfo.value.__cause__, SQLAlchemyError)


def test_execution_failure_becomes_query_execution_failed_error(sqlite_engine):
    engine, _sales = sqlite_engine
    # Selecting from a table that doesn't exist -> fails at execute time,
    # not at connect time.
    stmt = select(text("*")).select_from(text("does_not_exist"))
    built_query = _built_query(stmt)

    with pytest.raises(QueryExecutionFailedError) as excinfo:
        QueryExecutor(engine=engine).execute(built_query)

    assert isinstance(excinfo.value.__cause__, SQLAlchemyError)


def test_non_sqlalchemy_exception_passes_through(sqlite_engine):
    engine, sales = sqlite_engine

    class ExplodingConnection:
        def __enter__(self):
            raise TypeError("not a SQLAlchemy problem")

        def __exit__(self, *exc_info):
            return False

    fake_engine = MagicMock()
    fake_engine.connect.return_value = ExplodingConnection()
    built_query = _built_query(select(sales.c.id))

    with pytest.raises(TypeError):
        QueryExecutor(engine=fake_engine).execute(built_query)


# --------------------------------------------------------------------
# The exact statement is passed straight to connection.execute()
# --------------------------------------------------------------------


def test_exact_statement_passed_to_connection_execute(sqlite_engine):
    engine, sales = sqlite_engine
    stmt = select(sales.c.id)
    built_query = _built_query(stmt)

    fake_result = MagicMock()
    fake_result.keys.return_value = ["id"]
    fake_result.mappings.return_value = []

    fake_connection = MagicMock()
    fake_connection.execute.return_value = fake_result
    fake_connection.__enter__.return_value = fake_connection
    fake_connection.__exit__.return_value = False

    fake_engine = MagicMock()
    fake_engine.connect.return_value = fake_connection

    QueryExecutor(engine=fake_engine).execute(built_query)

    fake_connection.execute.assert_called_once_with(stmt)


# --------------------------------------------------------------------
# Engine resolution
# --------------------------------------------------------------------


def test_injected_engine_is_used_not_get_engine(monkeypatch, sqlite_engine):
    engine, sales = sqlite_engine

    def _fail_if_called():
        raise AssertionError("get_engine() should not be called when an engine is injected")

    monkeypatch.setattr(
        "etl.analytics.executor.executor.get_engine", _fail_if_called
    )

    stmt = select(sales.c.id)
    result = QueryExecutor(engine=engine).execute(_built_query(stmt))
    assert result.row_count == 3


def test_no_engine_falls_back_to_get_engine(monkeypatch, sqlite_engine):
    engine, sales = sqlite_engine
    monkeypatch.setattr(
        "etl.analytics.executor.executor.get_engine", lambda: engine
    )

    stmt = select(sales.c.id)
    result = QueryExecutor().execute(_built_query(stmt))
    assert result.row_count == 3