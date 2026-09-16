from __future__ import annotations

from dataclasses import dataclass

from openai import OpenAI

from etl.analytics.nl_query.parser import CompletionFn, CompletionRequest


@dataclass(frozen=True)
class OpenAICompletionConfig:
    """Configuration for the OpenAI completion provider."""

    model: str
    api_key: str


class OpenAICompletionProvider:
    """Adapter that exposes OpenAI as the NL parser CompletionFn."""

    def __init__(
        self,
        *,
        config: OpenAICompletionConfig,
        client: OpenAI | None = None,
    ) -> None:
        if not config.model.strip():
            raise ValueError(
                "OpenAI completion model must not be empty."
            )

        if client is None and not config.api_key:
            raise RuntimeError(
                "OpenAI API key is not configured."
            )

        self.config = config
        self.client = (
            client
            if client is not None
            else OpenAI(api_key=config.api_key)
        )

    def __call__(self, request: CompletionRequest) -> str:
        """Generate a completion using the OpenAI Responses API."""

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
    model: str,
    api_key: str,
) -> CompletionFn:
    """Create an OpenAI-backed CompletionFn."""

    return OpenAICompletionProvider(
        config=OpenAICompletionConfig(
            model=model,
            api_key=api_key,
        )
    )