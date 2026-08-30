"""Analytics API dependencies.

This module adapts the existing analytics pipeline to FastAPI without
moving business logic into the API layer.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from database.connection import session_scope
from etl.analytics.execution.executor import AnalyticalQueryExecutor
from etl.analytics.nl_query.parser import (
    CompletionFn,
    CompletionRequest,
    NLQueryParser,
    ParserConfig,
)
from etl.analytics.nl_query.providers.openai_provider import create_openai_completion
from etl.analytics.query import build_query
from etl.analytics.query.models import CompiledQuery, QueryRequest
from etl.analytics.response.builder import AnalyticalResponseBuilder
from etl.analytics.semantic.semantic_resolver import SemanticResolver
from etl.analytics.semantic.time_resolver import resolve_analytical_query_time
from etl.analytics.service.analytical_query_service import AnalyticalQueryService


def _completion_not_configured(request: CompletionRequest) -> str:
    raise RuntimeError(
        "Natural-language query completion provider is not configured."
    )


def get_nl_completion() -> CompletionFn:
    """Return the NL parser completion function.

    The project currently has no concrete LLM provider wired in, so this
    remains intentionally injectable for application/bootstrap code and tests.
    """

    return create_openai_completion()


class NaturalLanguageSemanticResolver:
    """Bridge question text to the QueryRequest expected by the query layer."""

    def __init__(
        self,
        parser: NLQueryParser,
        semantic_resolver: SemanticResolver,
        *,
        today: date | None = None,
    ) -> None:
        self.parser = parser
        self.semantic_resolver = semantic_resolver
        self.today = today

    def resolve(self, text: str) -> QueryRequest:
        parsed = self.parser.parse(text)
        resolved = self.semantic_resolver.resolve(parsed)
        bridged = resolved.to_analytical_query_request()
        time_resolved = resolve_analytical_query_time(bridged, today=self.today)
        return time_resolved.to_query_request()


class ExistingQueryBuilder:
    """Adapter for the module-level query builder function."""

    def build(self, request: QueryRequest) -> CompiledQuery:
        return build_query(request)


class CompiledQueryPassthroughValidator:
    """Match AnalyticalQueryService's validator slot.

    The real validation contract is validate_query(QueryRequest), and
    build_query(request) already invokes it before returning CompiledQuery.
    There is no separate compiled-query validator in the current codebase.
    """

    def validate(self, query: CompiledQuery) -> CompiledQuery:
        return query


def _raw_connection_from_session(session: Session) -> Any:
    """Return the raw DBAPI connection used by AnalyticalQueryExecutor."""

    return session.connection().connection


def build_analytics_service(
    *,
    db_session: Session,
    completion: CompletionFn,
    today: date | None = None,
) -> AnalyticalQueryService:
    parser = NLQueryParser(complete=completion, config=ParserConfig(today=today))
    resolver = NaturalLanguageSemanticResolver(
        parser=parser,
        semantic_resolver=SemanticResolver(),
        today=today,
    )
    executor = AnalyticalQueryExecutor(_raw_connection_from_session(db_session))

    return AnalyticalQueryService(
        semantic_resolver=resolver,
        query_builder=ExistingQueryBuilder(),
        query_validator=CompiledQueryPassthroughValidator(),
        executor=executor,
    )


def get_response_builder() -> AnalyticalResponseBuilder:
    return AnalyticalResponseBuilder()


def get_analytics_service() -> Iterator[AnalyticalQueryService]:
    completion = get_nl_completion()
    with session_scope() as db_session:
        yield build_analytics_service(
            db_session=db_session,
            completion=completion,
        )
