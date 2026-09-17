from __future__ import annotations

from unittest.mock import patch

import pytest
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

from database.connection import (
    build_database_url,
    get_engine,
    get_sessionmaker,
    session_scope,
)
from etl.analytics.config import Settings, get_settings


@pytest.fixture(autouse=True)
def clear_database_caches():
    """Ensure cached settings/database objects do not leak between tests."""
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()
    get_settings.cache_clear()

    yield

    get_engine.cache_clear()
    get_sessionmaker.cache_clear()
    get_settings.cache_clear()


@pytest.fixture
def settings() -> Settings:
    """Provide isolated database settings without loading .env."""
    return Settings(
        _env_file=None,  # type: ignore
        db_host="localhost",
        db_port=5432,
        db_name="test_db",
        db_user="test_user",
        db_password="test_password",
        db_echo=False,
        db_pool_size=5,
        db_max_overflow=10,
        db_connect_timeout=5,
        db_statement_timeout=30,
        db_pool_timeout=10,
    )


def test_build_database_url(settings: Settings):
    url = build_database_url(settings)

    assert isinstance(url, URL)
    assert url.drivername == "postgresql+psycopg2"
    assert url.username == "test_user"
    assert url.password == "test_password"
    assert url.host == "localhost"
    assert url.port == 5432
    assert url.database == "test_db"


def test_build_database_url_uses_application_settings():
    settings = Settings(
        _env_file=None,  # type: ignore
        db_host="db.example.com",
        db_port=5433,
        db_name="analytics",
        db_user="analytics_user",
        db_password="secret",
    )

    url = build_database_url(settings)

    assert url.host == "db.example.com"
    assert url.port == 5433
    assert url.database == "analytics"
    assert url.username == "analytics_user"
    assert url.password == "secret"


def test_build_database_url_uses_cached_settings_by_default():
    configured_settings = Settings(
        _env_file=None,  # type: ignore
        db_host="localhost",
        db_port=5432,
        db_name="analytics",
        db_user="analytics_user",
        db_password="secret",
    )

    with patch(
        "database.connection.get_settings",
        return_value=configured_settings,
    ) as mock_get_settings:
        url = build_database_url()

    mock_get_settings.assert_called_once()

    assert url.database == "analytics"
    assert url.username == "analytics_user"


def test_get_engine_uses_settings(settings: Settings):
    with (
        patch(
            "database.connection.get_settings",
            return_value=settings,
        ),
        patch("database.connection.create_engine") as mock_create_engine,
    ):
        get_engine()

    mock_create_engine.assert_called_once()

    kwargs = mock_create_engine.call_args.kwargs

    assert kwargs["echo"] is False
    assert kwargs["pool_size"] == 5
    assert kwargs["max_overflow"] == 10
    assert kwargs["pool_timeout"] == 10
    assert kwargs["pool_pre_ping"] is True
    assert kwargs["future"] is True

    connect_args = kwargs["connect_args"]

    assert connect_args["connect_timeout"] == 5
    assert connect_args["options"] == "-c statement_timeout=30000"

    database_url = mock_create_engine.call_args.args[0]

    assert database_url.drivername == "postgresql+psycopg2"
    assert database_url.database == "test_db"
    assert database_url.username == "test_user"


def test_get_engine_is_cached(settings: Settings):
    with (
        patch(
            "database.connection.get_settings",
            return_value=settings,
        ),
        patch(
            "database.connection.create_engine",
            return_value=object(),
        ) as mock_create_engine,
    ):
        first_engine = get_engine()
        second_engine = get_engine()

    assert first_engine is second_engine
    mock_create_engine.assert_called_once()


def test_get_sessionmaker_binds_to_engine(settings: Settings):
    fake_engine = object()

    with (
        patch(
            "database.connection.get_settings",
            return_value=settings,
        ),
        patch(
            "database.connection.create_engine",
            return_value=fake_engine,
        ),
        patch("database.connection.sessionmaker") as mock_sessionmaker,
    ):
        get_sessionmaker()

    mock_sessionmaker.assert_called_once_with(
        bind=fake_engine,
        autoflush=False,
        expire_on_commit=False,
    )


def test_get_sessionmaker_is_cached(settings: Settings):
    fake_sessionmaker = object()

    with (
        patch(
            "database.connection.get_settings",
            return_value=settings,
        ),
        patch(
            "database.connection.create_engine",
            return_value=object(),
        ),
        patch(
            "database.connection.sessionmaker",
            return_value=fake_sessionmaker,
        ) as mock_sessionmaker,
    ):
        first = get_sessionmaker()
        second = get_sessionmaker()

    assert first is second
    assert first is fake_sessionmaker
    mock_sessionmaker.assert_called_once()


def test_session_scope_commits_on_success():
    fake_session = type(
        "FakeSession",
        (),
        {
            "commit": lambda self: setattr(self, "committed", True),
            "rollback": lambda self: setattr(self, "rolled_back", True),
            "close": lambda self: setattr(self, "closed", True),
        },
    )()

    fake_session_factory = lambda: fake_session

    with patch(
        "database.connection.get_sessionmaker",
        return_value=fake_session_factory,
    ):
        with session_scope() as yielded_session:
            assert yielded_session is fake_session

    assert getattr(fake_session, "committed", False) is True
    assert getattr(fake_session, "closed", False) is True
    assert getattr(fake_session, "rolled_back", False) is False


def test_session_scope_rolls_back_on_exception():
    fake_session = type(
        "FakeSession",
        (),
        {
            "commit": lambda self: setattr(self, "committed", True),
            "rollback": lambda self: setattr(self, "rolled_back", True),
            "close": lambda self: setattr(self, "closed", True),
        },
    )()

    fake_session_factory = lambda: fake_session

    with patch(
        "database.connection.get_sessionmaker",
        return_value=fake_session_factory,
    ):
        with pytest.raises(RuntimeError, match="database failure"):
            with session_scope():
                raise RuntimeError("database failure")

    assert getattr(fake_session, "committed", False) is False
    assert getattr(fake_session, "rolled_back", False) is True
    assert getattr(fake_session, "closed", False) is True


def test_session_scope_reraises_original_exception():
    fake_session = type(
        "FakeSession",
        (),
        {
            "commit": lambda self: None,
            "rollback": lambda self: None,
            "close": lambda self: None,
        },
    )()

    with patch(
        "database.connection.get_sessionmaker",
        return_value=lambda: fake_session,
    ):
        error = ValueError("original error")

        with pytest.raises(ValueError) as exc_info:
            with session_scope():
                raise error

    assert exc_info.value is error