"""
Phase 9.2 -- Natural Language Query Parser.

Single responsibility:

    Natural language question
            |
            v
    LLM structured extraction
            |
            v
    AnalyticalQueryRequest        (ai.analytics.schemas)

This module deliberately does NOT:
  - resolve metric aliases against etl.analytics.metrics.registry (Phase 9.3)
  - validate dimensions against the registry (Phase 9.3)
  - compute relative dates like "this month" into real dates (Phase 9.4)
  - talk to a database, run build_query(), or execute SQL (Phase 8)

It also doesn't depend on any specific LLM SDK. Callers inject a
`CompletionFn` -- a plain callable of shape
`(system_prompt: str, user_message: str) -> str`. That keeps this
module unit-testable with a canned function and swappable across
providers.

Example wiring (illustrative; this sandbox has no network access to
actually run it):

    import anthropic
    client = anthropic.Anthropic()

    def complete(system_prompt: str, user_message: str) -> str:
        response = client.messages.create(
            model="<the model your deployment uses>",
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        return "".join(
            block.text for block in response.content if block.type == "text"
        )

    parser = NLQueryParser(complete=complete)
    request = parser.parse("What were total sales in August 2026?")
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable, Optional, Sequence

from etl.analytics.schemas import (
    AnalyticalQueryRequest,
    ComparisonSpec,
    FilterCondition,
    TimeRange,
)
from etl.analytics.nl_query.exceptions import (
    InvalidQuestionError,
    LLMCallError,
    LLMResponseFormatError,
    LLMResponseValidationError,
)
from etl.analytics.nl_query.prompts import MetricHint, build_system_prompt

# (system_prompt, user_message) -> raw model text. Bring your own LLM
# client; see the module docstring above for a wiring example.
CompletionFn = Callable[[str, str], str]

_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def _strip_code_fences(text: str) -> str:
    """LLMs frequently wrap JSON in ```json ... ``` even when told
    not to. Strip that before parsing rather than failing on it."""
    return _CODE_FENCE_RE.sub("", text.strip()).strip()


def _extract_json_object(text: str) -> str:
    """Best-effort: if the model added stray prose before/after the
    JSON object despite instructions, grab the outermost {...} span
    rather than failing outright."""
    stripped = _strip_code_fences(text)
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end < start:
        return stripped
    return stripped[start : end + 1]


def _parse_date(value: Any, *, field_name: str) -> Optional[date]:
    if value is None:
        return None
    if not isinstance(value, str):
        raise LLMResponseValidationError(
            f"{field_name} must be an ISO date string ('YYYY-MM-DD'), got {value!r}."
        )
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise LLMResponseValidationError(
            f"{field_name} {value!r} is not a valid ISO date ('YYYY-MM-DD')."
        ) from exc


def _time_range_from_json(data: Any) -> Optional[TimeRange]:
    """Convert an optional JSON time_range object into TimeRange."""

    if data is None:
        return None

    if not isinstance(data, dict):
        raise LLMResponseValidationError(
            f"time_range must be a JSON object, got {data!r}."
        )

    preset = data.get("preset")
    label = data.get("label")
    start = _parse_date(
        data.get("start"),
        field_name="time_range.start",
    )
    end = _parse_date(
        data.get("end"),
        field_name="time_range.end",
    )

    # Treat an omitted, empty, or fully-null time range as no time range.
    if (
        preset is None
        and label is None
        and start is None
        and end is None
    ):
        return None

    try:
        return TimeRange(
            preset=preset,
            label=label,
            start=start,
            end=end,
        )

    except ValueError as exc:
        raise LLMResponseValidationError(
            f"time_range: {exc}"
        ) from exc


def _filters_from_json(data: Any) -> tuple[FilterCondition, ...]:
    if data is None:
        return ()
    if not isinstance(data, list):
        raise LLMResponseValidationError(f"filters must be a JSON array, got {data!r}.")

    filters: list[FilterCondition] = []
    for i, entry in enumerate(data):
        if not isinstance(entry, dict):
            raise LLMResponseValidationError(
                f"filters[{i}] must be a JSON object, got {entry!r}."
            )
        dimension = entry.get("dimension")
        if not isinstance(dimension, str):
            raise LLMResponseValidationError(
                f"filters[{i}].dimension must be a string, got {dimension!r}."
            )
        try:
            filters.append(
                FilterCondition(
                    dimension=dimension,
                    operator=entry.get("operator", "eq"),
                    value=entry.get("value"),
                )
            )
        except (ValueError, TypeError) as exc:
            raise LLMResponseValidationError(f"filters[{i}]: {exc}") from exc
    return tuple(filters)


def _comparison_from_json(data: Any) -> Optional[ComparisonSpec]:
    if data is None:
        return None
    if not isinstance(data, dict) or "mode" not in data:
        raise LLMResponseValidationError(
            f"comparison must be a JSON object with a 'mode' field, got {data!r}."
        )
    try:
        return ComparisonSpec(mode=data["mode"])
    except ValueError as exc:
        raise LLMResponseValidationError(f"comparison: {exc}") from exc


def _request_from_json(data: dict[str, Any], *, raw_question: str) -> AnalyticalQueryRequest:
    metric = data.get("metric")
    if not metric or not isinstance(metric, str):
        raise LLMResponseValidationError(
            f"LLM response is missing a valid required 'metric' string field (got {metric!r})."
        )

    try:
        additional_metrics = tuple(data.get("additional_metrics") or ())
        dimensions = tuple(data.get("dimensions") or ())
    except TypeError as exc:
        raise LLMResponseValidationError(
            "additional_metrics/dimensions must be JSON arrays of strings."
        ) from exc

    try:
        return AnalyticalQueryRequest(
            metric=metric,
            additional_metrics=additional_metrics,
            dimensions=dimensions,
            filters=_filters_from_json(data.get("filters")),
            time_grain=data.get("time_grain"),
            time_range=_time_range_from_json(data.get("time_range")),
            limit=data.get("limit"),
            sort_by=data.get("sort_by"),
            sort_order=data.get("sort_order") or "desc",
            comparison=_comparison_from_json(data.get("comparison")),
            raw_question=raw_question,
        )
    except LLMResponseValidationError:
        raise
    except (ValueError, TypeError) as exc:
        raise LLMResponseValidationError(str(exc)) from exc


@dataclass(frozen=True)
class ParserConfig:
    """Optional grounding context injected into the system prompt.
    Purely for prompt quality -- never used to validate the LLM's
    output on this side. See MetricHint / build_system_prompt."""

    metric_hints: Sequence[MetricHint] = field(default_factory=tuple)
    dimension_hints: Sequence[str] = field(default_factory=tuple)
    today: Optional[date] = None


class NLQueryParser:
    """
    Turns a natural-language question into an AnalyticalQueryRequest
    using an injected LLM completion function.

        parser = NLQueryParser(complete=my_llm_complete_fn)
        request = parser.parse("What were total sales in August 2026?")

    Raises (see exceptions.py for the full hierarchy):
        InvalidQuestionError:       question is empty/whitespace-only.
        LLMCallError:               the injected `complete` raised.
        LLMResponseFormatError:     response text isn't usable JSON.
        LLMResponseValidationError: JSON parsed, but doesn't form a
                                     valid AnalyticalQueryRequest.
    """

    def __init__(self, complete: CompletionFn, *, config: Optional[ParserConfig] = None) -> None:
        self._complete = complete
        self._config = config or ParserConfig()

    def parse(self, question: str) -> AnalyticalQueryRequest:
        if not isinstance(question, str) or not question.strip():
            raise InvalidQuestionError("question must be a non-empty string.")

        system_prompt = build_system_prompt(
            metric_hints=self._config.metric_hints,
            dimension_hints=self._config.dimension_hints,
            today=self._config.today,
        )

        try:
            raw_response = self._complete(system_prompt, question)
        except Exception as exc:  # noqa: BLE001 - deliberately re-raised as our own type
            raise LLMCallError(f"LLM completion call failed: {exc}") from exc

        if not isinstance(raw_response, str) or not raw_response.strip():
            raise LLMResponseFormatError("LLM returned an empty or non-string response.")

        json_text = _extract_json_object(raw_response)
        try:
            data = json.loads(json_text)
        except json.JSONDecodeError as exc:
            raise LLMResponseFormatError(
                f"LLM response was not valid JSON ({exc}). Raw response: {raw_response!r}"
            ) from exc

        if not isinstance(data, dict):
            raise LLMResponseFormatError(
                f"LLM response JSON must be an object, got {type(data).__name__}."
            )

        return _request_from_json(data, raw_question=question)
