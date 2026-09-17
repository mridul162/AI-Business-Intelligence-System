"""
Application composition root for the analytics system.
"""

from __future__ import annotations

from functools import partial

from etl.analytics.application.analytics_application import AnalyticsApplication
from etl.analytics.config import Settings, get_settings
from etl.analytics.executor.executor import QueryExecutor
from etl.analytics.merger import ResultMerger
from etl.analytics.metrics.registry import get_metric
from etl.analytics.nl_query.parser import CompletionFn, NLQueryParser
from etl.analytics.providers import (
    create_openai_completion,
)
from etl.analytics.orchestration import AnalyticsQueryOrchestrator
from etl.analytics.planner.query_planner import plan_query
from etl.analytics.response.builder import AnalyticalResponseBuilder
from etl.analytics.semantic import SemanticResolver
from etl.analytics.sql.sql_builder import build_query


def get_nl_completion(settings: Settings) -> CompletionFn:
    return create_openai_completion(
        model=settings.nl_query_model,
        api_key=settings.openai_api_key,
        timeout=settings.llm_timeout,
        max_attempts=settings.llm_max_attempts,
        retry_initial_backoff=settings.llm_retry_initial_backoff,
        retry_max_backoff=settings.llm_retry_max_backoff,
    )

def create_analytics_application(
    *,
    settings: Settings,
    completion: CompletionFn | None = None,
    executor: QueryExecutor | None = None,
) -> AnalyticsApplication:
    """
    Construct the analytics application and its dependencies.

    This function is the composition root for the analytics pipeline.
    """
    completion = completion or get_nl_completion(settings)

    planner = partial(
        plan_query,
        resolve_metric=get_metric,
    )

    builder = partial(
        build_query,
        get_metric=get_metric,
    )

    orchestrator = AnalyticsQueryOrchestrator(
        planner=planner,
        builder=builder,
        executor=executor if executor is not None else QueryExecutor(),
        merger=ResultMerger(),
    )

    return AnalyticsApplication(
        parser=NLQueryParser(
            complete=completion,
        ),
        semantic_resolver=SemanticResolver(),
        query_orchestrator=orchestrator,
        response_builder=AnalyticalResponseBuilder(),
    )


def get_analytics_application() -> AnalyticsApplication:
    """
    Return an analytics application using the application's settings.
    """
    return create_analytics_application(
        settings=get_settings(),
    )