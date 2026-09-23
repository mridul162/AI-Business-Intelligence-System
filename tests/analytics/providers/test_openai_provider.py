"""OpenAI provider tests for NL query structured outputs."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

import openai

from etl.analytics.nl_query import CompletionRequest
from etl.analytics.providers.openai_provider import (
    OpenAICompletionConfig,
    OpenAICompletionProvider,
    create_openai_completion,
)
from etl.analytics.providers.pricing import ModelPricing
from etl.observability.metrics import metrics

@pytest.fixture(autouse=True)
def reset_metrics():
    metrics.reset()
    yield
    metrics.reset()


@dataclass
class FakeResponse:
    output_text: str

def _timeout_error() -> openai.APITimeoutError:
    return openai.APITimeoutError(request=Mock())


def _connection_error() -> openai.APIConnectionError:
    return openai.APIConnectionError(request=Mock())


class FakeResponses:
    def __init__(
        self,
        output_text: str | None = None,
        errors: list[Exception] | None = None,
    ) -> None:
        self.output_text = output_text
        self.errors = list(errors or [])
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> FakeResponse:
        self.calls.append(kwargs)

        if self.errors:
            error = self.errors.pop(0)
            raise error

        return FakeResponse(self.output_text or "")


class FakeClient:
    def __init__(
        self,
        output_text: str | None = None,
        errors: list[Exception] | None = None,
    ) -> None:
        self.responses = FakeResponses(
            output_text=output_text,
            errors=errors,
        )


def _completion_request() -> CompletionRequest:
    return CompletionRequest(
        system_prompt="system",
        user_message="question",
        response_schema={"type": "object"},
    )


def test_openai_provider_passes_strict_json_schema_to_responses_api() -> None:
    client = FakeClient('{"metric": "capital_invested"}')

    provider = OpenAICompletionProvider(
        client=client,  # type: ignore[arg-type]
        config=OpenAICompletionConfig(
            model="gpt-test",
            api_key="test-key",
        ),
    )

    schema = {
        "type": "object",
        "properties": {
            "metric": {"type": "string", "enum": ["capital_invested"]},
        },
        "required": ["metric"],
        "additionalProperties": False,
    }

    output = provider(
        CompletionRequest(
            system_prompt="system",
            user_message="question",
            response_schema=schema,
        )
    )

    assert output == '{"metric": "capital_invested"}'
    assert len(client.responses.calls) == 1

    call = client.responses.calls[0]

    assert call["model"] == "gpt-test"
    assert call["instructions"] == "system"
    assert call["input"] == "question"
    assert call["text"] == {
        "format": {
            "type": "json_schema",
            "name": "analytical_query_request",
            "description": (
                "A structured analytical query request using "
                "canonical registry metric identifiers."
            ),
            "schema": schema,
            "strict": True,
        }
    }


def test_openai_provider_strips_output() -> None:
    client = FakeClient('  {"metric": "capital_invested"}  ')

    provider = OpenAICompletionProvider(
        client=client,  # type: ignore[arg-type]
        config=OpenAICompletionConfig(
            model="gpt-test",
            api_key="test-key",
        ),
    )

    output = provider(_completion_request())

    assert output == '{"metric": "capital_invested"}'


def test_openai_provider_records_optional_usage() -> None:
    client = FakeClient('{"metric": "capital_invested"}')
    client.responses.create = Mock(
        return_value=SimpleNamespace(
            output_text='{"metric": "capital_invested"}',
            usage=SimpleNamespace(
                input_tokens=11,
                output_tokens=7,
                total_tokens=18,
            ),
        )
    )

    provider = OpenAICompletionProvider(
        client=client,  # type: ignore[arg-type]
        config=OpenAICompletionConfig(model="gpt-test", api_key="test-key"),
    )

    provider(_completion_request())

    assert len(provider.usage_records) == 1
    record = provider.usage_records[0]
    assert record.input_tokens == 11
    assert record.output_tokens == 7
    assert record.total_tokens == 18
    assert record.attempt == 1


def test_openai_provider_handles_missing_usage() -> None:
    client = FakeClient('{"metric": "capital_invested"}')
    provider = OpenAICompletionProvider(
        client=client,  # type: ignore[arg-type]
        config=OpenAICompletionConfig(model="gpt-test", api_key="test-key"),
    )

    provider(_completion_request())

    assert len(provider.usage_records) == 1
    assert provider.usage_records[0].total_tokens is None


def test_openai_provider_rejects_empty_model() -> None:
    with pytest.raises(
        ValueError,
        match="OpenAI completion model must not be empty",
    ):
        OpenAICompletionProvider(
            client=FakeClient("{}"),  # type: ignore[arg-type]
            config=OpenAICompletionConfig(
                model="   ",
                api_key="test-key",
            ),
        )


def test_openai_provider_requires_api_key_without_client() -> None:
    with pytest.raises(
        RuntimeError,
        match="OpenAI API key is not configured",
    ):
        OpenAICompletionProvider(
            config=OpenAICompletionConfig(
                model="gpt-test",
                api_key="",
            ),
        )


def test_openai_provider_allows_missing_api_key_with_injected_client() -> None:
    client = FakeClient("{}")

    provider = OpenAICompletionProvider(
        client=client,  # type: ignore[arg-type]
        config=OpenAICompletionConfig(
            model="gpt-test",
            api_key="",
        ),
    )

    assert provider.client is client


def test_openai_provider_rejects_empty_output() -> None:
    client = FakeClient("   ")

    provider = OpenAICompletionProvider(
        client=client,  # type: ignore[arg-type]
        config=OpenAICompletionConfig(
            model="gpt-test",
            api_key="test-key",
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="OpenAI returned an empty completion",
    ):
        provider(_completion_request())


def test_openai_provider_passes_timeout_to_openai_client() -> None:
    config = OpenAICompletionConfig(
        model="gpt-test",
        api_key="test-key",
        timeout=15.0,
    )

    with patch(
        "etl.analytics.providers.openai_provider.OpenAI"
    ) as mock_openai:
        provider = OpenAICompletionProvider(config=config)

    mock_openai.assert_called_once_with(
        api_key="test-key",
        timeout=15.0,
        max_retries=0,
    )
    assert provider.client is mock_openai.return_value


def test_openai_provider_does_not_retry_successful_request() -> None:
    client = FakeClient('{"metric": "capital_invested"}')

    provider = OpenAICompletionProvider(
        client=client,  # type: ignore[arg-type]
        config=OpenAICompletionConfig(
            model="gpt-test",
            api_key="test-key",
            max_attempts=3,
        ),
    )

    output = provider(_completion_request())

    assert output == '{"metric": "capital_invested"}'
    assert len(client.responses.calls) == 1


def test_openai_provider_retries_timeout_error() -> None:
    client = FakeClient(
        output_text='{"metric": "capital_invested"}',
        errors=[
            _timeout_error(),
        ],
    )

    provider = OpenAICompletionProvider(
        client=client,  # type: ignore[arg-type]
        config=OpenAICompletionConfig(
            model="gpt-test",
            api_key="test-key",
            max_attempts=3,
            retry_initial_backoff=0.5,
            retry_max_backoff=2.0,
        ),
    )

    with patch(
        "etl.analytics.providers.openai_provider.time.sleep"
    ) as mock_sleep:
        output = provider(_completion_request())

    assert output == '{"metric": "capital_invested"}'
    assert len(client.responses.calls) == 2
    mock_sleep.assert_called_once_with(0.5)


def test_openai_provider_retries_connection_error() -> None:
    client = FakeClient(
        output_text='{"metric": "capital_invested"}',
        errors=[
            _connection_error(),
        ],
    )

    provider = OpenAICompletionProvider(
        client=client,  # type: ignore[arg-type]
        config=OpenAICompletionConfig(
            model="gpt-test",
            api_key="test-key",
        ),
    )

    with patch(
        "etl.analytics.providers.openai_provider.time.sleep"
    ) as mock_sleep:
        output = provider(_completion_request())

    assert output == '{"metric": "capital_invested"}'
    assert len(client.responses.calls) == 2
    mock_sleep.assert_called_once_with(0.5)


def test_openai_provider_does_not_retry_non_retryable_error() -> None:
    client = FakeClient(
        errors=[
            ValueError("invalid request"),
        ],
    )

    provider = OpenAICompletionProvider(
        client=client,  # type: ignore[arg-type]
        config=OpenAICompletionConfig(
            model="gpt-test",
            api_key="test-key",
            max_attempts=3,
        ),
    )

    with patch(
        "etl.analytics.providers.openai_provider.time.sleep"
    ) as mock_sleep:
        with pytest.raises(ValueError, match="invalid request"):
            provider(_completion_request())

    assert len(client.responses.calls) == 1
    mock_sleep.assert_not_called()


def test_openai_provider_respects_max_attempts() -> None:
    client = FakeClient(
        errors=[
            _timeout_error(),
            _timeout_error(),
            _timeout_error(),
        ],
    )

    provider = OpenAICompletionProvider(
        client=client,  # type: ignore[arg-type]
        config=OpenAICompletionConfig(
            model="gpt-test",
            api_key="test-key",
            max_attempts=3,
        ),
    )

    with patch(
        "etl.analytics.providers.openai_provider.time.sleep"
    ) as mock_sleep:
        with pytest.raises(openai.APITimeoutError):
            provider(_completion_request())

    assert len(client.responses.calls) == 3
    assert mock_sleep.call_count == 2


def test_openai_provider_uses_exponential_backoff() -> None:
    client = FakeClient(
        errors=[
            _timeout_error(),
            _timeout_error(),
            _timeout_error(),
        ],
    )

    provider = OpenAICompletionProvider(
        client=client,  # type: ignore[arg-type]
        config=OpenAICompletionConfig(
            model="gpt-test",
            api_key="test-key",
            max_attempts=3,
            retry_initial_backoff=0.5,
            retry_max_backoff=10.0,
        ),
    )

    with patch(
        "etl.analytics.providers.openai_provider.time.sleep"
    ) as mock_sleep:
        with pytest.raises(openai.APITimeoutError):
            provider(_completion_request())

    assert mock_sleep.call_args_list == [
        ((0.5,),),
        ((1.0,),),
    ]


def test_openai_provider_caps_exponential_backoff() -> None:
    client = FakeClient(
        errors=[
            _timeout_error(),
            _timeout_error(),
            _timeout_error(),
        ],
    )

    provider = OpenAICompletionProvider(
        client=client,  # type: ignore[arg-type]
        config=OpenAICompletionConfig(
            model="gpt-test",
            api_key="test-key",
            max_attempts=3,
            retry_initial_backoff=2.0,
            retry_max_backoff=2.0,
        ),
    )

    with patch(
        "etl.analytics.providers.openai_provider.time.sleep"
    ) as mock_sleep:
        with pytest.raises(openai.APITimeoutError):
            provider(_completion_request())

    assert mock_sleep.call_args_list == [
        ((2.0,),),
        ((2.0,),),
    ]


def test_openai_provider_validates_max_attempts() -> None:
    with pytest.raises(
        ValueError,
        match="max_attempts must be at least 1",
    ):
        OpenAICompletionProvider(
            client=FakeClient("{}"),  # type: ignore[arg-type]
            config=OpenAICompletionConfig(
                model="gpt-test",
                api_key="test-key",
                max_attempts=0,
            ),
        )


def test_openai_provider_validates_timeout() -> None:
    with pytest.raises(
        ValueError,
        match="timeout must be greater than 0",
    ):
        OpenAICompletionProvider(
            client=FakeClient("{}"),  # type: ignore[arg-type]
            config=OpenAICompletionConfig(
                model="gpt-test",
                api_key="test-key",
                timeout=0,
            ),
        )


def test_openai_provider_validates_negative_initial_backoff() -> None:
    with pytest.raises(
        ValueError,
        match="retry initial backoff must not be negative",
    ):
        OpenAICompletionProvider(
            client=FakeClient("{}"),  # type: ignore[arg-type]
            config=OpenAICompletionConfig(
                model="gpt-test",
                api_key="test-key",
                retry_initial_backoff=-1,
            ),
        )


def test_openai_provider_validates_negative_max_backoff() -> None:
    with pytest.raises(
        ValueError,
        match="retry maximum backoff must not be negative",
    ):
        OpenAICompletionProvider(
            client=FakeClient("{}"),  # type: ignore[arg-type]
            config=OpenAICompletionConfig(
                model="gpt-test",
                api_key="test-key",
                retry_max_backoff=-1,
            ),
        )


def test_create_openai_completion_passes_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeProvider:
        def __init__(
            self,
            *,
            config: OpenAICompletionConfig,
        ) -> None:
            captured["config"] = config

    monkeypatch.setattr(
        "etl.analytics.providers.openai_provider.OpenAICompletionProvider",
        FakeProvider,
    )

    completion = create_openai_completion(
        model="gpt-test",
        api_key="test-key",
        timeout=15.0,
        max_attempts=4,
        retry_initial_backoff=0.25,
        retry_max_backoff=3.0,
    )

    config = captured["config"]

    assert isinstance(config, OpenAICompletionConfig)
    assert config.model == "gpt-test"
    assert config.api_key == "test-key"
    assert config.timeout == 15.0
    assert config.max_attempts == 4
    assert config.retry_initial_backoff == 0.25
    assert config.retry_max_backoff == 3.0
    assert isinstance(completion, FakeProvider)


def make_openai_error(error_type: type[Exception]) -> Exception:
    """Create an OpenAI SDK exception suitable for testing."""
    request = Mock()

    if error_type is openai.APITimeoutError:
        return error_type(request=request)

    if error_type is openai.APIConnectionError:
        return error_type(request=request)

    response = Mock()
    response.status_code = {
        openai.RateLimitError: 429,
        openai.InternalServerError: 500,
        openai.ConflictError: 409,
        openai.AuthenticationError: 401,
        openai.BadRequestError: 400,
        openai.PermissionDeniedError: 403,
        openai.NotFoundError: 404,
        openai.UnprocessableEntityError: 422,
    }[error_type]

    return error_type(
        message="test error", # type: ignore 
        response=response, # type: ignore
        body=None, # type: ignore
    )


@pytest.mark.parametrize(
    "error_type",
    [
        openai.APITimeoutError,
        openai.APIConnectionError,
        openai.RateLimitError,
        openai.InternalServerError,
        openai.ConflictError,
    ],
)
def test_openai_provider_retries_transient_openai_errors(
    error_type: type[Exception],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = Mock()

    error = make_openai_error(error_type)

    client.responses.create.side_effect = [
        error,
        Mock(output_text='{"metric": "gross_sales"}'),
    ]

    provider = OpenAICompletionProvider(
        client=client,
        config=OpenAICompletionConfig(
            model="test-model",
            api_key="test-key",
            max_attempts=2,
            retry_initial_backoff=0,
            retry_max_backoff=0,
        ),
    )

    result = provider(
        Mock(
            system_prompt="system",
            user_message="question",
            response_schema={},
        )
    )

    assert result == '{"metric": "gross_sales"}'
    assert client.responses.create.call_count == 2


def test_openai_provider_records_request_metrics() -> None:
    client = FakeClient('{"metric": "capital_invested"}')

    client.responses.create = Mock(
        return_value=SimpleNamespace(
            output_text='{"metric": "capital_invested"}',
            usage=SimpleNamespace(
                input_tokens=11,
                output_tokens=7,
                total_tokens=18,
            ),
        )
    )

    provider = OpenAICompletionProvider(
        client=client,  # type: ignore[arg-type]
        config=OpenAICompletionConfig(
            model="gpt-test",
            api_key="test-key",
        ),
    )

    provider(_completion_request())

    snapshot = metrics.snapshot()

    assert snapshot["counters"]["llm_requests_total"] == 1          #type: ignore
    assert snapshot["counters"]["llm_requests_successful"] == 1     #type: ignore
    assert snapshot["counters"].get("llm_requests_failed", 0) == 0  #type: ignore
    assert snapshot["counters"]["llm_attempts_total"] == 1          #type: ignore
    assert snapshot["counters"].get("llm_retries_total", 0) == 0    #type: ignore

    assert snapshot["totals"]["llm_input_tokens"] == 11             #type: ignore 
    assert snapshot["totals"]["llm_total_tokens"] == 18             #type: ignore


def test_openai_provider_records_retry_metrics() -> None:
    client = FakeClient(
        output_text='{"metric": "capital_invested"}',
        errors=[
            _timeout_error(),
        ],
    )

    provider = OpenAICompletionProvider(
        client=client,  # type: ignore[arg-type]
        config=OpenAICompletionConfig(
            model="gpt-test",
            api_key="test-key",
            max_attempts=3,
            retry_initial_backoff=0,
            retry_max_backoff=0,
        ),
    )

    provider(_completion_request())

    snapshot = metrics.snapshot()

    assert snapshot["counters"]["llm_requests_total"] == 1 #type: ignore
    assert snapshot["counters"]["llm_requests_successful"] == 1 #type: ignore
    assert snapshot["counters"].get("llm_requests_failed", 0) == 0 #type: ignore
    assert snapshot["counters"]["llm_attempts_total"] == 2 #type: ignore
    assert snapshot["counters"]["llm_retries_total"] == 1 #type: ignore


def test_openai_provider_records_final_failure_metrics() -> None:
    client = FakeClient(
        errors=[
            _timeout_error(),
            _timeout_error(),
        ],
    )

    provider = OpenAICompletionProvider(
        client=client,  # type: ignore[arg-type]
        config=OpenAICompletionConfig(
            model="gpt-test",
            api_key="test-key",
            max_attempts=2,
            retry_initial_backoff=0,
            retry_max_backoff=0,
        ),
    )

    with pytest.raises(openai.APITimeoutError):
        provider(_completion_request())

    snapshot = metrics.snapshot()

    assert snapshot["counters"]["llm_requests_total"] == 1 # type: ignore
    assert snapshot["counters"].get("llm_requests_successful", 0) == 0 # type: ignore
    assert snapshot["counters"]["llm_requests_failed"] == 1 # type: ignore
    assert snapshot["counters"]["llm_attempts_total"] == 2  # type: ignore
    assert snapshot["counters"]["llm_retries_total"] == 1 # type: ignore

    assert snapshot["totals"].get("llm_input_tokens", 0) == 0 # type: ignore
    assert snapshot["totals"].get("llm_output_tokens", 0) == 0 # type: ignore
    assert snapshot["totals"].get("llm_total_tokens", 0) == 0 # type: ignore


def test_openai_provider_records_llm_latency_metric() -> None:
    client = FakeClient('{"metric": "capital_invested"}')

    client.responses.create = Mock(
        return_value=SimpleNamespace(
            output_text='{"metric": "capital_invested"}',
            usage=SimpleNamespace(
                input_tokens=11,
                output_tokens=7,
                total_tokens=18,
            ),
        )
    )

    provider = OpenAICompletionProvider(
        client=client,  # type: ignore[arg-type]
        config=OpenAICompletionConfig(
            model="gpt-test",
            api_key="test-key",
        ),
    )

    provider(_completion_request())

    snapshot = metrics.snapshot()

    timing = next(
        value
        for key, value in snapshot["timings"].items() # type: ignore
        if "llm_duration_ms" in key
    )

    assert timing["count"] == 1
    assert timing["total_ms"] >= 0
    assert timing["min_ms"] >= 0
    assert timing["max_ms"] >= 0


def test_openai_provider_records_estimated_cost() -> None:
    client = FakeClient('{"metric": "capital_invested"}')
    client.responses.create = Mock(
        return_value=SimpleNamespace(
            output_text='{"metric": "capital_invested"}',
            usage=SimpleNamespace(
                input_tokens=1_000_000,
                output_tokens=500_000,
                total_tokens=1_500_000,
            ),
        )
    )

    provider = OpenAICompletionProvider(
        client=client,  # type: ignore[arg-type]
        config=OpenAICompletionConfig(
            model="gpt-test",
            api_key="test-key",
            pricing=ModelPricing(
                input_price_per_million=1.0,
                output_price_per_million=2.0,
            ),
        ),
    )

    provider(_completion_request())

    snapshot = metrics.snapshot()

    assert snapshot["totals"]["llm_estimated_cost"] == 2.0 # type: ignore
 