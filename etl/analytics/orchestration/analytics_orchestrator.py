"""
Coordinates the existing planner/builder/executor/merger components
into one deterministic execution workflow.

    
            v
       Query Planner  ->  QueryPlan | MultiQueryPlan
            v
        SQL Builder   ->  BuiltQuery  (once per QueryPlan)
            v
      Query Executor  ->  ExecutionResult  (once per BuiltQuery)
            v
      Result Merger   ->  MergedResult  (only for MultiQueryPlan)
            v
      AnalyticalResult

This module coordinates; it does not think. It contains no SQL, no
metric/dimension logic, no semantic resolution, no merge algorithm,
and no natural-language generation -- those all already live in the
components it calls. Multi-query execution is sequential (plan 1,
then plan 2, ... then merge) -- no concurrency, no partial results:
if any plan's build/execute fails, the whole request fails and the
merger is never called.

Errors from the planner/builder/executor/merger are NEVER caught or
translated here -- they propagate with their original type so the
layer above this one can log/classify them. The only exceptions this
module raises itself are in errors.py, and only for the
orchestrator's own coordination logic (bad constructor args, an
unrecognized planner return type).
"""

from __future__ import annotations

from typing import Any, Callable, Protocol

from etl.analytics.context.request_context import TenantScope
from etl.analytics.executor.execution_models import ExecutionResult
from etl.analytics.merger.merge_models import ExecutedQuery, MergedResult
from etl.analytics.planner.query_plan import MultiQueryPlan, QueryPlan, QueryPlanResult
from etl.analytics.sql.sql_models import BuiltQuery

from .errors import InvalidPlanResultError, OrchestratorConfigurationError
from .orchestration_models import AnalyticalResult

import logging

from etl.observability.timing import timed_stage

logger = logging.getLogger(__name__)

Planner = Callable[[Any], QueryPlanResult]
Builder = Callable[..., BuiltQuery]


class ExecutorLike(Protocol):
    def execute(self, built_query: BuiltQuery) -> ExecutionResult: ...


class MergerLike(Protocol):
    def merge(
        self, multi_plan: MultiQueryPlan, executed_queries: tuple[ExecutedQuery, ...]
    ) -> MergedResult: ...


class AnalyticsQueryOrchestrator:
    """
    Executes a resolved analytical request end-to-end.

    All four dependencies are injected rather than constructed
    internally, so tests can supply fakes/mocks for each without
    exercising real SQL/DB code. Each is used exactly as it already
    exists elsewhere in the project -- this class calls them, it
    doesn't wrap or reimplement their behavior:

        planner:  request -> QueryPlan | MultiQueryPlan
                  (e.g. functools.partial(plan_query, resolve_metric=get_metric))
        builder:  QueryPlan -> BuiltQuery
                  (e.g. functools.partial(build_query, get_metric=get_metric))
        executor: an object with .execute(BuiltQuery) -> ExecutionResult
                  (e.g. a QueryExecutor instance)
        merger:   an object with .merge(MultiQueryPlan, tuple[ExecutedQuery, ...]) -> MergedResult
                  (e.g. a ResultMerger instance)
    """

    def __init__(
        self,
        planner: Planner,
        builder: Builder,
        executor: ExecutorLike,
        merger: MergerLike,
    ) -> None:
        if planner is None or builder is None or executor is None or merger is None:
            raise OrchestratorConfigurationError(
                "AnalyticsQueryOrchestrator requires a planner, builder, "
                "executor, and merger -- none may be None."
            )
        self._planner = planner
        self._builder = builder
        self._executor = executor
        self._merger = merger

    def execute(
            self, 
            request: Any,
            *,
            tenant_scope: TenantScope | None = None,
    ) -> AnalyticalResult:
        """
        Run `request` through plan -> build -> execute -> (merge) and
        return one canonical AnalyticalResult.

        Raises whatever the planner/builder/executor/merger raise,
        unchanged, plus InvalidPlanResultError if the planner returns
        something that is neither a QueryPlan nor a MultiQueryPlan.
        """
        with timed_stage(
            "planning",
            logger=logger,
        ):
            plan_result = self._planner(request)

        if isinstance(plan_result, QueryPlan):
            return self._execute_single(plan_result, tenant_scope=tenant_scope) # type: ignore

        if isinstance(plan_result, MultiQueryPlan):
            return self._execute_multi(plan_result, tenant_scope=tenant_scope) # type: ignore

        raise InvalidPlanResultError(
            f"Planner returned {type(plan_result)!r}, expected QueryPlan "
            f"or MultiQueryPlan."
        )

    def _execute_single(
        self, 
        plan: QueryPlan,
        *,
        tenant_scope: TenantScope | None = None
    ) -> AnalyticalResult:
        with timed_stage(
            "sql_building",
            logger=logger,
        ):
            built_query = self._builder(plan, tenant_scope=tenant_scope)

        with timed_stage(
            "database_execution",
            logger=logger,
        ):
            execution_result = self._executor.execute(built_query)

        return AnalyticalResult.from_execution_result(execution_result)

    def _execute_multi(
        self, 
        multi_plan: MultiQueryPlan,
        *,
        tenant_scope: TenantScope | None = None
    ) -> AnalyticalResult:
        executed_queries: list[ExecutedQuery] = []

        for index, plan in enumerate(multi_plan.plans):
            with timed_stage(
                "sql_building",
                logger=logger,
                plan_index=index,
            ):
                built_query = self._builder(plan, tenant_scope=tenant_scope)

            with timed_stage(
                "database_execution",
                logger=logger,
                plan_index=index,
            ):
                execution_result = self._executor.execute(built_query)

            executed_queries.append(
                ExecutedQuery(
                    built_query=built_query,
                    result=execution_result,
                )
            )

        with timed_stage(
            "result_merging",
            logger=logger,
        ):
            merged_result = self._merger.merge(
                multi_plan,
                tuple(executed_queries),
            )

        return AnalyticalResult.from_merged_result(merged_result)