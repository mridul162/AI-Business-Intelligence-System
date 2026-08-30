"""
OpenAI completion provider for natural-language analytical queries.

This module adapts the OpenAI Responses API to the CompletionFn contract
used by NLQueryParser:

    CompletionRequest -> str
"""

from __future__ import annotations

from dataclasses import dataclass

from openai import OpenAI

from etl.analytics.nl_query.parser import CompletionFn, CompletionRequest
from etl.config.settings import get_settings


@dataclass(frozen=True)
class OpenAICompletionConfig:
    """Configuration for the OpenAI completion provider."""

    model: str


class OpenAICompletionProvider:
    """Adapter that exposes OpenAI as the NL parser CompletionFn."""

    def __init__(
        self,
        *,
        client: OpenAI | None = None,
        config: OpenAICompletionConfig | None = None,
    ) -> None:
        settings = get_settings()

        self.config = config or OpenAICompletionConfig(
            model=settings.nl_query_model,
        )

        if not self.config.model.strip():
            raise ValueError(
                "OpenAI completion model must not be empty."
            )

        if client is not None:
            self.client = client
            return

        if not settings.openai_api_key:
            raise RuntimeError(
                "OpenAI API key is not configured. "
                "Set OPENAI_API_KEY in the environment or .env file."
            )

        self.client = OpenAI(
            api_key=settings.openai_api_key,
        )

    def __call__(self, request: CompletionRequest) -> str:
        """
        Generate a completion using the OpenAI Responses API.

        The provider intentionally returns raw model text. JSON parsing
        and validation belong to NLQueryParser.
        """

        response = self.client.responses.create(
            model=self.config.model,
            instructions=request.system_prompt,
            input=request.user_message,
            text={
                "format": {
                    "type": "json_schema",
                    "name": "analytical_query_request",
                    "description": (
                        "A structured analytical query request using "
                        "canonical registry metric identifiers."
                    ),
                    "schema": request.response_schema,
                    "strict": True,
                }
            },
        )

        output = response.output_text

        if not output or not output.strip():
            raise RuntimeError(
                "OpenAI returned an empty completion for the "
                "natural-language analytical query."
            )

        return output.strip()


def create_openai_completion(
    *,
    model: str | None = None,
) -> CompletionFn:
    """Create a CompletionFn backed by OpenAI."""

    settings = get_settings()

    selected_model = (
        model.strip()
        if model is not None
        else settings.nl_query_model
    )

    if not selected_model:
        raise ValueError(
            "OpenAI completion model must not be empty."
        )

    provider = OpenAICompletionProvider(
        config=OpenAICompletionConfig(
            model=selected_model,
        )
    )

    return provider
