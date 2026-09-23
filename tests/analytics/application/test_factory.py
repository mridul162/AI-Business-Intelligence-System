from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from etl.analytics.application.analytics_application import AnalyticsApplication
from etl.analytics.application.factory import (
    create_analytics_application,
    get_analytics_application,
    get_nl_completion,
)
from etl.analytics.config import Settings
from etl.analytics.nl_query.parser import (
    CompletionFn,
    CompletionRequest,
    NLQueryParser,
)
from etl.analytics.response.builder import AnalyticalResponseBuilder
from etl.analytics.semantic import SemanticResolver


def make_settings() -> Settings:
    """Create isolated test settings without loading .env."""
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
        db_slow_query_threshold_ms=500.0,
    )


def test_create_analytics_application_returns_application() -> None:
    settings = make_settings()
    completion = Mock()

    application = create_analytics_application(
        settings=settings,
        completion=completion,
    )

    assert isinstance(application, AnalyticsApplication)


def test_create_analytics_application_injects_completion_provider() -> None:
    settings = make_settings()
    completion = Mock()

    application = create_analytics_application(
        settings=settings,
        completion=completion,
    )

    assert isinstance(application.parser, NLQueryParser)
    assert application.parser._complete is completion


def test_create_analytics_application_creates_semantic_resolver() -> None:
    settings = make_settings()
    completion = Mock()

    application = create_analytics_application(
        settings=settings,
        completion=completion,
    )

    assert isinstance(application.semantic_resolver, SemanticResolver)


def test_create_analytics_application_creates_response_builder() -> None:
    settings = make_settings()
    completion = Mock()

    application = create_analytics_application(
        settings=settings,
        completion=completion,
    )

    assert isinstance(
        application.response_builder,
        AnalyticalResponseBuilder,
    )


def test_create_analytics_application_uses_supplied_executor() -> None:
    settings = make_settings()
    completion = Mock()
    executor = Mock()

    with patch(
        "etl.analytics.application.factory.AnalyticsQueryOrchestrator"
    ) as mock_orchestrator:
        create_analytics_application(
            settings=settings,
            completion=completion,
            executor=executor,
        )

    mock_orchestrator.assert_called_once()

    kwargs = mock_orchestrator.call_args.kwargs

    assert kwargs["executor"] is executor


def test_create_analytics_application_creates_executor_when_not_supplied() -> None:
    settings = make_settings()
    completion = Mock()

    with (
        patch(
            "etl.analytics.application.factory.QueryExecutor"
        ) as mock_executor,
        patch(
            "etl.analytics.application.factory.AnalyticsQueryOrchestrator"
        ) as mock_orchestrator,
    ):
        executor = mock_executor.return_value

        create_analytics_application(
            settings=settings,
            completion=completion,
        )

    mock_executor.assert_called_once_with(
        slow_query_threshold_ms=500.0,
    )

    kwargs = mock_orchestrator.call_args.kwargs

    assert kwargs["executor"] is executor


def test_create_analytics_application_creates_result_merger() -> None:
    settings = make_settings()
    completion = Mock()

    with (
        patch(
            "etl.analytics.application.factory.ResultMerger"
        ) as mock_merger,
        patch(
            "etl.analytics.application.factory.AnalyticsQueryOrchestrator"
        ) as mock_orchestrator,
    ):
        merger = mock_merger.return_value

        create_analytics_application(
            settings=settings,
            completion=completion,
        )

    mock_merger.assert_called_once()

    kwargs = mock_orchestrator.call_args.kwargs

    assert kwargs["merger"] is merger


def test_create_analytics_application_wires_orchestrator_dependencies() -> None:
    settings = make_settings()
    completion = Mock()

    with patch(
        "etl.analytics.application.factory.AnalyticsQueryOrchestrator"
    ) as mock_orchestrator:
        create_analytics_application(
            settings=settings,
            completion=completion,
        )

    kwargs = mock_orchestrator.call_args.kwargs

    assert kwargs["planner"] is not None
    assert kwargs["builder"] is not None
    assert kwargs["executor"] is not None
    assert kwargs["merger"] is not None


def test_get_analytics_application_uses_application_settings() -> None:
    settings = make_settings()
    application = Mock()

    with (
        patch(
            "etl.analytics.application.factory.get_settings",
            return_value=settings,
        ) as mock_get_settings,
        patch(
            "etl.analytics.application.factory.create_analytics_application",
            return_value=application,
        ) as mock_create,
    ):
        result = get_analytics_application()

    mock_get_settings.assert_called_once()
    mock_create.assert_called_once_with(
        settings=settings,
    )
    assert result is application


def test_get_nl_completion_is_used_when_completion_not_supplied() -> None:
    settings = make_settings()
    completion = Mock()

    with patch(
        "etl.analytics.application.factory.get_nl_completion",
        return_value=completion,
    ) as mock_get_completion:
        application = create_analytics_application(
            settings=settings,
        )

    mock_get_completion.assert_called_once_with(settings)
    assert application.parser._complete is completion


def test_get_nl_completion_passes_all_settings_to_openai_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        _env_file=None,  # type: ignore
        nl_query_model="gpt-test",
        openai_api_key="test-key",
        llm_timeout=15.0,
        llm_max_attempts=4,
        llm_retry_initial_backoff=0.25,
        llm_retry_max_backoff=3.0,
        db_name="test-db",
        db_user="test-user",
    )

    captured: dict[str, object] = {}

    def fake_create_openai_completion(
        *,
        model: str,
        api_key: str,
        timeout: float,
        max_attempts: int,
        retry_initial_backoff: float,
        retry_max_backoff: float,
    ) -> CompletionFn:
        captured["model"] = model
        captured["api_key"] = api_key
        captured["timeout"] = timeout
        captured["max_attempts"] = max_attempts
        captured["retry_initial_backoff"] = retry_initial_backoff
        captured["retry_max_backoff"] = retry_max_backoff

        def completion(request: CompletionRequest) -> str:
            return "{}"

        return completion

    monkeypatch.setattr(
        "etl.analytics.application.factory.create_openai_completion",
        fake_create_openai_completion,
    )

    completion = get_nl_completion(settings)

    assert callable(completion)

    assert captured == {
        "model": "gpt-test",
        "api_key": "test-key",
        "timeout": 15.0,
        "max_attempts": 4,
        "retry_initial_backoff": 0.25,
        "retry_max_backoff": 3.0,
    }