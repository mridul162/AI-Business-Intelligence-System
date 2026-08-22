"""
Exceptions for the Phase 9.2 NL query parser.

Kept as one small hierarchy so callers can catch broadly
(`NLQueryParseError`) or narrowly, and so it's obvious at a glance
which stage of parse() a failure came from:

    question text
        │
        ▼  (bad/empty input)
    InvalidQuestionError
        │
        ▼  complete(system_prompt, question)
    LLMCallError                (the injected completion fn raised)
        │
        ▼  raw text response
    LLMResponseFormatError      (not JSON / not an object at all)
        │
        ▼  parsed JSON dict
    LLMResponseValidationError  (valid JSON, but not a valid request:
                                  missing "metric", bad enum value,
                                  bad date string, etc.)
        │
        ▼
    AnalyticalQueryRequest
"""

from __future__ import annotations


class NLQueryParseError(Exception):
    """Base class for anything that goes wrong turning a natural
    language question into an AnalyticalQueryRequest."""


class InvalidQuestionError(NLQueryParseError):
    """Raised when the input question itself is unusable (empty /
    whitespace-only) before any LLM call is made."""


class LLMCallError(NLQueryParseError):
    """Raised when the injected completion function itself raises
    (network error, auth failure, rate limit, etc). Wraps the
    original exception."""


class LLMResponseFormatError(NLQueryParseError):
    """Raised when the LLM's raw text response isn't usable as JSON
    at all -- empty response, non-JSON prose with no extractable
    object, or JSON that isn't an object."""


class LLMResponseValidationError(NLQueryParseError):
    """Raised when the LLM's response parses as JSON but doesn't
    produce a structurally valid AnalyticalQueryRequest -- a missing
    required field, an operator/preset/grain outside the known
    vocabulary, a malformed date string, etc. Wraps the underlying
    ValueError from the schema's own validation where applicable."""
