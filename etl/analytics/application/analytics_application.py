from __future__ import annotations

from datetime import date
from typing import Callable, Protocol

from etl.analytics.orchestration import (
    AnalyticsQueryOrchestrator,
    AnalyticalResult,
)
from etl.analytics.nl_query.parser import NLQueryParser
from etl.analytics.response.builder import (
    AnalyticalResponse,
    AnalyticalResponseBuilder,
)
from etl.analytics.schemas import AnalyticalQueryRequest
from etl.analytics.semantic import (
    ResolvedAnalyticalQuery,
    SemanticResolver,
)
from etl.analytics.semantic.time_resolver import resolve_analytical_query_time

import logging

logger = logging.getLogger(__name__)


class TimeResolverFn(Protocol):
    """Resolve relative time information into an explicit query time range."""

    def __call__(
        self,
        query: AnalyticalQueryRequest,
        *,
        today: date | None = None,
    ) -> AnalyticalQueryRequest:
        ...


class AnalyticsApplication:
    """
    Top-level application boundary for the analytics use case.

    Coordinates the user-facing pipeline:

        Natural language
            -> Parser
            -> Semantic resolution
            -> Time resolution
            -> Analytical query orchestration
            -> Response building
            -> AnalyticalResponse

    This class contains orchestration only. It does not implement:
        - natural-language parsing
        - semantic resolution
        - time-range calculations
        - query planning
        - SQL generation
        - database execution
        - result merging
        - response formatting
    """

    def __init__(
        self,
        parser: NLQueryParser,
        semantic_resolver: SemanticResolver,
        query_orchestrator: AnalyticsQueryOrchestrator,
        response_builder: AnalyticalResponseBuilder,
        time_resolver: TimeResolverFn = resolve_analytical_query_time, # type: ignore
    ) -> None:
        self.parser = parser
        self.semantic_resolver = semantic_resolver
        self.query_orchestrator = query_orchestrator
        self.response_builder = response_builder
        self.time_resolver = time_resolver

    def query(
        self,
        question: str,
        *,
        today: date | None = None,
    ) -> AnalyticalResponse:
        """
        Execute the complete natural-language analytics use case.

        Parameters
        ----------
        question:
            User's natural-language analytical question.

        today:
            Optional reference date used for deterministic relative-time
            resolution. Primarily useful for testing.

        Returns
        -------
        AnalyticalResponse
            Public response contract for the analytics application.
        """

        logger.info("analytics_query_started")

        try:

            parsed_request = self.parser.parse(question)

            resolved_query: ResolvedAnalyticalQuery = (
                self.semantic_resolver.resolve(parsed_request)
            )

            analytical_request = resolved_query.to_analytical_query_request()

            resolved_request = self.time_resolver(
                analytical_request,
                today=today,
            )

            analytical_result: AnalyticalResult = (
                self.query_orchestrator.execute(resolved_request)
            )

            response = self.response_builder.build(
                resolved_request,
                analytical_result,
            )

            logger.info("analytics_query_completed")

            return response

        except Exception:
            logger.exception("analytics_query_failed")
            raise