"""OpenAI provider tests for NL query structured outputs."""

from __future__ import annotations

from dataclasses import dataclass

from etl.analytics.nl_query import CompletionRequest
from etl.analytics.nl_query.providers.openai_provider import (
    OpenAICompletionConfig,
    OpenAICompletionProvider,
)


@dataclass
class FakeResponse:
    output_text: str


class FakeResponses:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> FakeResponse:
        self.calls.append(kwargs)
        return FakeResponse('{"metric": "capital_invested"}')


class FakeClient:
    def __init__(self) -> None:
        self.responses = FakeResponses()


def test_openai_provider_passes_strict_json_schema_to_responses_api() -> None:
    client = FakeClient()
    provider = OpenAICompletionProvider(
        client=client,  # type: ignore[arg-type]
        config=OpenAICompletionConfig(model="gpt-test"),
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
