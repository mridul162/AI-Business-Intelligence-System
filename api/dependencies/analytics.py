"""Analytics API dependencies."""

from __future__ import annotations

from functools import partial

from etl.analytics.application.analytics_application import AnalyticsApplication
from etl.analytics.executor.executor import QueryExecutor
from etl.analytics.merger import ResultMerger
from etl.analytics.metrics.registry import get_metric
from etl.analytics.nl_query.parser import (
    CompletionFn,
    NLQueryParser,
)
from etl.analytics.nl_query.providers.openai_provider import create_openai_completion
from etl.analytics.orchestration import AnalyticsQueryOrchestrator
from etl.analytics.planner.query_planner import plan_query
from etl.analytics.response.builder import AnalyticalResponseBuilder
from etl.analytics.semantic import SemanticResolver
from etl.analytics.sql.sql_builder import build_query


def get_nl_completion() -> CompletionFn:
    """Return the configured natural-language completion provider."""
    return create_openai_completion()


def build_analytics_application(
    *,
    completion: CompletionFn,
    executor: QueryExecutor | None = None,
) -> AnalyticsApplication:
    """Build the application boundary and its analytics pipeline."""

    planner = partial(plan_query, resolve_metric=get_metric)
    builder = partial(build_query, get_metric=get_metric)
    orchestrator = AnalyticsQueryOrchestrator(
        planner=planner,
        builder=builder,
        executor=executor if executor is not None else QueryExecutor(),
        merger=ResultMerger(),
    )

    return AnalyticsApplication(
        parser=NLQueryParser(complete=completion),
        semantic_resolver=SemanticResolver(),
        query_orchestrator=orchestrator,
        response_builder=AnalyticalResponseBuilder(),
    )


def get_analytics_application() -> AnalyticsApplication:
    return build_analytics_application(completion=get_nl_completion())
