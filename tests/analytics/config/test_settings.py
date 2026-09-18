"""Tests for analytics application settings."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from etl.analytics.config.settings import Settings, get_settings


_REQUIRED_DB_ENV = {
    "AIBI_DB_NAME": "test_db",
    "AIBI_DB_USER": "test_user",
}


def _set_required_db_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set the minimum required database configuration."""
    for name, value in _REQUIRED_DB_ENV.items():
        monkeypatch.setenv(name, value)


@pytest.fixture(autouse=True)
def clear_settings_cache() -> None:
    """Prevent cached settings from leaking between tests."""
    get_settings.cache_clear()


def test_required_database_settings_are_loaded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_required_db_env(monkeypatch)

    settings = Settings()  # type: ignore

    assert settings.db_name == "test_db"
    assert settings.db_user == "test_user"


def test_database_defaults_are_applied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_required_db_env(monkeypatch)

    settings = Settings()  # type: ignore

    assert settings.db_host == "localhost"
    assert settings.db_port == 5432
    assert settings.db_password == ""
    assert settings.db_echo is False
    assert settings.db_pool_size == 5
    assert settings.db_max_overflow == 10

    assert settings.db_connect_timeout == 5
    assert settings.db_statement_timeout == 30
    assert settings.db_pool_timeout == 10

    assert settings.environment == "development"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("true", True),
        ("false", False),
        ("1", True),
        ("0", False),
        ("yes", True),
        ("no", False),
        ("on", True),
        ("off", False),
    ],
)
def test_db_echo_parses_boolean_values(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
    expected: bool,
) -> None:
    _set_required_db_env(monkeypatch)
    monkeypatch.setenv("AIBI_DB_ECHO", value)

    settings = Settings()  # type: ignore

    assert settings.db_echo is expected


def test_environment_variables_override_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_required_db_env(monkeypatch)

    monkeypatch.setenv("AIBI_ENVIRONMENT", "production")
    monkeypatch.setenv("AIBI_JWT_SECRET_KEY", "production-secret-key-0123456789")
    monkeypatch.setenv("AIBI_DB_HOST", "postgres.example.com")
    monkeypatch.setenv("AIBI_DB_PORT", "5433")
    monkeypatch.setenv("AIBI_DB_PASSWORD", "secret")
    monkeypatch.setenv("AIBI_DB_POOL_SIZE", "20")
    monkeypatch.setenv("AIBI_DB_MAX_OVERFLOW", "30")
    monkeypatch.setenv("AIBI_DB_CONNECT_TIMEOUT", "15")
    monkeypatch.setenv("AIBI_DB_STATEMENT_TIMEOUT", "60")
    monkeypatch.setenv("AIBI_DB_POOL_TIMEOUT", "20")

    settings = Settings()  # type: ignore[call-arg]

    assert settings.environment == "production"
    assert settings.db_host == "postgres.example.com"
    assert settings.db_port == 5433
    assert settings.db_password == "secret"
    assert settings.db_pool_size == 20
    assert settings.db_max_overflow == 30

    assert settings.db_connect_timeout == 15
    assert settings.db_statement_timeout == 60
    assert settings.db_pool_timeout == 20


@pytest.mark.parametrize(
    "variable",
    [
        "AIBI_DB_CONNECT_TIMEOUT",
        "AIBI_DB_STATEMENT_TIMEOUT",
        "AIBI_DB_POOL_TIMEOUT",
    ],
)
@pytest.mark.parametrize("value", ["0", "-1"])
def test_timeout_settings_must_be_positive(
    monkeypatch: pytest.MonkeyPatch,
    variable: str,
    value: str,
) -> None:
    _set_required_db_env(monkeypatch)
    monkeypatch.setenv(variable, value)

    with pytest.raises(ValidationError):
        Settings()  # type: ignore[call-arg]


@pytest.mark.parametrize(
    ("variable", "value"),
    [
        ("AIBI_DB_POOL_SIZE", "0"),
        ("AIBI_DB_POOL_SIZE", "-1"),
        ("AIBI_DB_MAX_OVERFLOW", "-1"),
    ],
)
def test_pool_settings_reject_invalid_values(
    monkeypatch: pytest.MonkeyPatch,
    variable: str,
    value: str,
) -> None:
    _set_required_db_env(monkeypatch)
    monkeypatch.setenv(variable, value)

    with pytest.raises(ValidationError):
        Settings()  # type: ignore[call-arg]


@pytest.mark.parametrize(
    "missing_variable",
    ["AIBI_DB_NAME", "AIBI_DB_USER"],
)
def test_missing_required_database_setting_raises_validation_error(
    monkeypatch: pytest.MonkeyPatch,
    missing_variable: str,
) -> None:
    _set_required_db_env(monkeypatch)
    monkeypatch.delenv(missing_variable)

    with pytest.raises(ValidationError):
        Settings()  # type: ignore[call-arg]


def test_get_settings_returns_cached_instance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_required_db_env(monkeypatch)

    first = get_settings()
    second = get_settings()

    assert first is second


def test_rate_and_cost_control_defaults_are_explicit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_required_db_env(monkeypatch)

    settings = Settings()  # type: ignore

    assert settings.rate_limit_requests == 30
    assert settings.rate_limit_window_seconds == 60
    assert settings.rate_limit_burst == 10
    assert settings.max_queries_per_request == 5
    assert settings.max_result_rows == 1000


def test_rate_and_cost_controls_load_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_required_db_env(monkeypatch)
    monkeypatch.setenv("AIBI_RATE_LIMIT_REQUESTS", "12")
    monkeypatch.setenv("AIBI_RATE_LIMIT_WINDOW_SECONDS", "30")
    monkeypatch.setenv("AIBI_RATE_LIMIT_BURST", "4")
    monkeypatch.setenv("AIBI_MAX_QUERIES_PER_REQUEST", "3")
    monkeypatch.setenv("AIBI_MAX_RESULT_ROWS", "250")

    settings = Settings()  # type: ignore

    assert settings.rate_limit_requests == 12
    assert settings.rate_limit_window_seconds == 30
    assert settings.rate_limit_burst == 4
    assert settings.max_queries_per_request == 3
    assert settings.max_result_rows == 250


def test_production_cannot_disable_authentication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_required_db_env(monkeypatch)
    monkeypatch.setenv("AIBI_ENVIRONMENT", "production")
    monkeypatch.setenv("AIBI_AUTH_ENABLED", "false")

    with pytest.raises(ValidationError):
        Settings()  # type: ignore


def test_production_rejects_the_development_jwt_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_required_db_env(monkeypatch)
    monkeypatch.setenv("AIBI_ENVIRONMENT", "production")

    with pytest.raises(ValidationError):
        Settings()  # type: ignore