"""
OpenAI completion provider for natural-language analytical queries.

This module adapts the OpenAI Responses API to the CompletionFn contract
used by NLQueryParser:

    (system_prompt: str, user_message: str) -> str
"""

from __future__ import annotations

from dataclasses import dataclass

from openai import OpenAI

from etl.analytics.nl_query.parser import CompletionFn
from etl.config.settings import get_settings


@dataclass(frozen=True)
class OpenAICompletionConfig:
    """Configuration for the OpenAI completion provider."""

    model: str = "gpt-4.1-mini"


class OpenAICompletionProvider:
    """Adapter that exposes OpenAI as the NL parser CompletionFn."""

    def __init__(
        self,
        *,
        client: OpenAI | None = None,
        config: OpenAICompletionConfig | None = None,
    ) -> None:
        self.config = config or OpenAICompletionConfig()

        if client is not None:
            self.client = client
            return

        settings = get_settings()

        if not settings.openai_api_key:
            raise RuntimeError(
                "OpenAI API key is not configured. "
                "Set OPENAI_API_KEY in the environment or .env file."
            )

        self.client = OpenAI(
            api_key=settings.openai_api_key,
        )

    def __call__(
        self,
        system_prompt: str,
        user_message: str,
    ) -> str:
        """Generate a completion using the OpenAI Responses API."""

        response = self.client.responses.create(
            model=self.config.model,
            instructions=system_prompt,
            input=user_message,
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

    config = OpenAICompletionConfig(
        model=model or settings.nl_query_model,
    )

    provider = OpenAICompletionProvider(config=config)

    return provider