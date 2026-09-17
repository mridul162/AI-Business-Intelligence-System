from __future__ import annotations

import time
from dataclasses import dataclass

import openai
from openai import OpenAI

from etl.analytics.nl_query.parser import CompletionFn, CompletionRequest


@dataclass(frozen=True)
class OpenAICompletionConfig:
    """Configuration for the OpenAI completion provider."""

    model: str
    api_key: str
    timeout: float = 20.0
    max_attempts: int = 3
    retry_initial_backoff: float = 0.5
    retry_max_backoff: float = 2.0


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

        if not config.api_key and client is None:
            raise RuntimeError(
                "OpenAI API key is not configured."
            )

        if config.max_attempts < 1:
            raise ValueError(
                "OpenAI completion max_attempts must be at least 1."
            )

        if config.timeout <= 0:
            raise ValueError(
                "OpenAI completion timeout must be greater than 0."
            )

        if config.retry_initial_backoff < 0:
            raise ValueError(
                "OpenAI retry initial backoff must not be negative."
            )

        if config.retry_max_backoff < 0:
            raise ValueError(
                "OpenAI retry maximum backoff must not be negative."
            )

        self.config = config

        self.client = (
            client
            if client is not None
            else OpenAI(
                api_key=config.api_key,
                timeout=config.timeout,
                max_retries=0,
            )
        )

    def __call__(self, request: CompletionRequest) -> str:
        """Generate a completion using the OpenAI Responses API."""

        last_error: Exception | None = None

        for attempt in range(1, self.config.max_attempts + 1):
            try:
                return self._complete(request)
            except Exception as exc:
                last_error = exc

                if (
                    not self._is_retryable_error(exc)
                    or attempt >= self.config.max_attempts
                ):
                    raise

                delay = self._calculate_backoff(attempt)
                time.sleep(delay)

        # Defensive guard. The loop either returns or raises.
        assert last_error is not None
        raise last_error

    def _complete(self, request: CompletionRequest) -> str:
        """Execute a single OpenAI completion attempt."""

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

    @staticmethod
    def _is_retryable_error(exc: Exception) -> bool:
        """
        Return whether an OpenAI error should be retried.

        Retry classification is intentionally kept separate from the
        completion logic so retry behavior can be tested independently.
        """

        return isinstance(
            exc,
            (
                openai.APITimeoutError,
                openai.APIConnectionError,
                openai.RateLimitError,
                openai.InternalServerError,
                openai.ConflictError,
            ),
        )

    def _calculate_backoff(self, attempt: int) -> float:
        """Calculate bounded exponential backoff for a retry."""

        delay = self.config.retry_initial_backoff * (2 ** (attempt - 1))

        return min(
            delay,
            self.config.retry_max_backoff,
        )


def create_openai_completion(
    *,
    model: str,
    api_key: str,
    timeout: float = 20.0,
    max_attempts: int = 3,
    retry_initial_backoff: float = 0.5,
    retry_max_backoff: float = 2.0,
) -> CompletionFn:
    """Create an OpenAI-backed CompletionFn."""

    return OpenAICompletionProvider(
        config=OpenAICompletionConfig(
            model=model,
            api_key=api_key,
            timeout=timeout,
            max_attempts=max_attempts,
            retry_initial_backoff=retry_initial_backoff,
            retry_max_backoff=retry_max_backoff,
        )
    )