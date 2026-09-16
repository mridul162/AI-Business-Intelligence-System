"""OpenAI provider tests for NL query structured outputs."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from etl.analytics.nl_query import CompletionRequest
from etl.analytics.nl_query.providers.openai_provider import (
    OpenAICompletionConfig,
    OpenAICompletionProvider,
    create_openai_completion,
)


@dataclass
class FakeResponse:
    output_text: str


class FakeResponses:
    def __init__(self, output_text: str) -> None:
        self.output_text = output_text
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> FakeResponse:
        self.calls.append(kwargs)
        return FakeResponse(self.output_text)


class FakeClient:
    def __init__(self, output_text: str) -> None:
        self.responses = FakeResponses(output_text)


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

    output = provider(
        CompletionRequest(
            system_prompt="system",
            user_message="question",
            response_schema={"type": "object"},
        )
    )

    assert output == '{"metric": "capital_invested"}'


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
        provider(
            CompletionRequest(
                system_prompt="system",
                user_message="question",
                response_schema={"type": "object"},
            )
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
        "etl.analytics.nl_query.providers.openai_provider.OpenAICompletionProvider",
        FakeProvider,
    )

    completion = create_openai_completion(
        model="gpt-test",
        api_key="test-key",
    )

    config = captured["config"]

    assert isinstance(config, OpenAICompletionConfig)
    assert config.model == "gpt-test"
    assert config.api_key == "test-key"
    assert isinstance(completion, FakeProvider)