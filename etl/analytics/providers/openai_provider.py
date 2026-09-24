from __future__ import annotations

import time
from dataclasses import dataclass

import openai
from openai import OpenAI

from etl.analytics.context.request_context import get_request_context
from etl.analytics.nl_query.parser import CompletionFn, CompletionRequest
from etl.analytics.providers.usage import LLMUsageRecord, UsageRecorder
from etl.observability.metrics import metrics
from etl.analytics.providers.pricing import ModelPricing


@dataclass(frozen=True)
class OpenAICompletionConfig:
    """Configuration for the OpenAI completion provider."""

    model: str
    api_key: str
    timeout: float = 20.0
    max_attempts: int = 3
    retry_initial_backoff: float = 0.5
    retry_max_backoff: float = 2.0
    pricing: ModelPricing | None = None


class OpenAICompletionProvider:
    """Adapter that exposes OpenAI as the NL parser CompletionFn."""

    def __init__(
        self,
        *,
        config: OpenAICompletionConfig,
        client: OpenAI | None = None,
        usage_recorder: UsageRecorder | None = None,
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
        self.usage_recorder = usage_recorder
        self.usage_records: list[LLMUsageRecord] = []

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

        metrics.increment("llm_requests_total")

        last_error: Exception | None = None

        for attempt in range(1, self.config.max_attempts + 1):
            metrics.increment("llm_attempts_total")

            started_at = time.perf_counter()

            try:
                output, response = self._complete(request)

                latency_seconds = time.perf_counter() - started_at

                self._record_usage(
                    response,
                    attempt,
                    latency_seconds,
                )

                metrics.increment("llm_requests_successful")

                return output

            except Exception as exc:
                last_error = exc

                if (
                    not self._is_retryable_error(exc)
                    or attempt >= self.config.max_attempts
                ):
                    metrics.increment("llm_requests_failed")
                    raise

                metrics.increment("llm_retries_total")

                delay = self._calculate_backoff(attempt)
                time.sleep(delay)

        # Defensive guard. The loop either returns or raises.
        assert last_error is not None
        metrics.increment("llm_requests_failed")
        raise last_error

    def _complete(self, request: CompletionRequest) -> tuple[str, object]:
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

        return output.strip(), response

    def _record_usage(
        self,
        response: object,
        attempt: int,
        latency_seconds: float,
    ) -> None:
        usage = getattr(response, "usage", None)

        request_context = get_request_context()

        input_tokens = _usage_value(
            usage,
            "input_tokens",
        )
        output_tokens = _usage_value(
            usage,
            "output_tokens",
        )
        total_tokens = _usage_value(
            usage,
            "total_tokens",
        )

        if input_tokens is not None:
            metrics.add("llm_input_tokens", input_tokens)

        if output_tokens is not None:
            metrics.add("llm_output_tokens", output_tokens)

        if total_tokens is not None:
            metrics.add("llm_total_tokens", total_tokens)

        if (
            self.config.pricing is not None
            and input_tokens is not None
            and output_tokens is not None
        ):
            estimated_cost = self.config.pricing.calculate_cost(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
            metrics.add("llm_estimated_cost", estimated_cost)

        record = LLMUsageRecord(
            request_id=request_context.request_id if request_context else None,
            model=self.config.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            latency_seconds=latency_seconds,
            attempt=attempt,
        )

        self.usage_records.append(record)

        if self.usage_recorder is not None:
            self.usage_recorder.record(record)

        metrics.observe(
            "llm_duration_ms",
            latency_seconds * 1000,
            labels={"model": self.config.model},
        )

            
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


def _usage_value(usage: object, field: str) -> int | None:
    """Read optional SDK usage fields without assuming usage is present."""
    value = getattr(usage, field, None) if usage is not None else None
    return value if isinstance(value, int) else None


def create_openai_completion(
    *,
    model: str,
    api_key: str,
    timeout: float = 20.0,
    max_attempts: int = 3,
    retry_initial_backoff: float = 0.5,
    retry_max_backoff: float = 2.0,
    pricing: ModelPricing | None = None,
    usage_recorder: UsageRecorder | None = None,
) -> CompletionFn:
    """Create an OpenAI-backed CompletionFn."""

    config = OpenAICompletionConfig(
        model=model,
        api_key=api_key,
        timeout=timeout,
        max_attempts=max_attempts,
        retry_initial_backoff=retry_initial_backoff,
        retry_max_backoff=retry_max_backoff,
        pricing=pricing,
    )

    if usage_recorder is None:
        return OpenAICompletionProvider(
            config=config,
        )

    return OpenAICompletionProvider(
        config=config,
        usage_recorder=usage_recorder,
    )