"""
Natural Language Query Parser (Phase 9.2) -- public surface.

    from etl.analytics.nl_query import (
        NLQueryParser,
        ParserConfig,
        CompletionFn,
        MetricHint,
        build_system_prompt,
        NLQueryParseError,
        InvalidQuestionError,
        LLMCallError,
        LLMResponseFormatError,
        LLMResponseValidationError,
    )

    parser = NLQueryParser(complete=my_llm_complete_fn)
    request = parser.parse("What were total sales in August 2026?")
    # request is an ai.analytics.schemas.AnalyticalQueryRequest,
    # possibly still carrying an unresolved TimeRange -- pass it on to
    # Phase 9.3 (metric/dimension resolution) and Phase 9.4 (time
    # resolution) before calling request.to_query_request().
"""

from etl.analytics.nl_query.exceptions import (
    InvalidQuestionError,
    LLMCallError,
    LLMResponseFormatError,
    LLMResponseValidationError,
    NLQueryParseError,
)
from etl.analytics.nl_query.parser import CompletionFn, NLQueryParser, ParserConfig
from etl.analytics.nl_query.prompts import MetricHint, build_system_prompt

__all__ = [
    "NLQueryParser",
    "ParserConfig",
    "CompletionFn",
    "MetricHint",
    "build_system_prompt",
    "NLQueryParseError",
    "InvalidQuestionError",
    "LLMCallError",
    "LLMResponseFormatError",
    "LLMResponseValidationError",
]
