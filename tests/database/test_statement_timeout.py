from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError


TEST_DB_URL = os.environ.get(
    "AIBI_INTEGRATION_TEST_DB_URL",
    "postgresql+psycopg2://aibi_test:aibi_test_pw@localhost:5432/aibi_test_db",
)


@pytest.fixture(scope="module")
def timeout_engine() -> Engine:
    engine = create_engine(
        TEST_DB_URL,
        future=True,
        connect_args={
            "options": "-c statement_timeout=100",
        },
    )

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:
        engine.dispose()
        pytest.skip(f"Integration test Postgres not reachable: {exc}")

    yield engine
    engine.dispose()


def test_postgresql_statement_timeout_is_enforced(
    timeout_engine: Engine,
) -> None:
    with pytest.raises(DBAPIError):
        with timeout_engine.connect() as connection:
            connection.execute(text("SELECT pg_sleep(1)"))