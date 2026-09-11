from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from etl.analytics.executor.execution_models import ExecutionResult
from etl.analytics.merger.merge_models import ExecutedQuery, MergedResult
from etl.analytics.orchestration import (
    AnalyticalResult,
    AnalyticsQueryOrchestrator,
    InvalidPlanResultError,
    OrchestratorConfigurationError,
)
from etl.analytics.planner.query_plan import MergeStrategy, MultiQueryPlan, QueryPlan
from etl.analytics.sql.sql_models import BuiltQuery


def make_plan(source_view: str, metrics: tuple[str, ...] = ("m",)) -> QueryPlan:
    return QueryPlan(source_view=source_view, metrics=metrics)


def make_built_query(plan: QueryPlan, tag: str) -> BuiltQuery:
    return BuiltQuery(
        statement=tag,  # not a real SQLAlchemy statement -- fine, the # type: ignore
                        # orchestrator never inspects it, only passes it through
        plan=plan,
        metric_output_fields=plan.metrics,
        dimension_fields=(),
        time_bucket_alias=None,
    )


def make_execution_result(value: Decimal) -> ExecutionResult:
    return ExecutionResult(
        columns=("m",),
        rows=({"m": value},),
        row_count=1,
        duration_seconds=0.001,
    )


@pytest.fixture
def fakes():
    planner = MagicMock(name="planner")
    builder = MagicMock(name="builder")
    executor = MagicMock(name="executor")
    merger = MagicMock(name="merger")
    return planner, builder, executor, merger


# --------------------------------------------------------------------
# Single QueryPlan path
# --------------------------------------------------------------------


def test_single_plan_calls_planner_builder_executor_not_merger(fakes):
    planner, builder, executor, merger = fakes
    plan = make_plan("v_sales")
    built_query = make_built_query(plan, "A")
    execution_result = make_execution_result(Decimal("100"))

    planner.return_value = plan
    builder.return_value = built_query
    executor.execute.return_value = execution_result

    orchestrator = AnalyticsQueryOrchestrator(planner, builder, executor, merger)
    request = object()
    orchestrator.execute(request)

    planner.assert_called_once_with(request)
    builder.assert_called_once_with(plan)
    executor.execute.assert_called_once_with(built_query)
    merger.merge.assert_not_called()


def test_single_plan_result_propagated_correctly(fakes):
    planner, builder, executor, merger = fakes
    plan = make_plan("v_sales")
    built_query = make_built_query(plan, "A")
    execution_result = make_execution_result(Decimal("42.50"))

    planner.return_value = plan
    builder.return_value = built_query
    executor.execute.return_value = execution_result

    orchestrator = AnalyticsQueryOrchestrator(planner, builder, executor, merger)
    result = orchestrator.execute(object())

    assert isinstance(result, AnalyticalResult)
    assert result.columns == ("m",)
    assert result.rows == ({"m": Decimal("42.50")},)
    assert result.row_count == 1
    assert result.merge_strategy is MergeStrategy.NONE


# --------------------------------------------------------------------
# MultiQueryPlan path
# --------------------------------------------------------------------


def test_multi_plan_two_plans_builder_and_executor_called_twice_merger_once(fakes):
    planner, builder, executor, merger = fakes
    plan_a = make_plan("v_sales")
    plan_b = make_plan("v_expenses")
    multi_plan = MultiQueryPlan(plans=(plan_a, plan_b), merge_strategy=MergeStrategy.SIDE_BY_SIDE)

    built_a, built_b = make_built_query(plan_a, "A"), make_built_query(plan_b, "B")
    result_a, result_b = make_execution_result(Decimal("1")), make_execution_result(Decimal("2"))

    planner.return_value = multi_plan
    builder.side_effect = {plan_a: built_a, plan_b: built_b}.get
    executor.execute.side_effect = {built_a: result_a, built_b: result_b}.get
    merger.merge.return_value = MergedResult(
        columns=("m",), rows=({"m": Decimal("3")},), row_count=1, merge_strategy=MergeStrategy.SIDE_BY_SIDE
    )

    orchestrator = AnalyticsQueryOrchestrator(planner, builder, executor, merger)
    orchestrator.execute(object())

    assert builder.call_count == 2
    assert executor.execute.call_count == 2
    merger.merge.assert_called_once()


def test_multi_plan_three_plans_all_processed(fakes):
    planner, builder, executor, merger = fakes
    plans = [make_plan(f"v_{i}") for i in range(3)]
    multi_plan = MultiQueryPlan(plans=tuple(plans), merge_strategy=MergeStrategy.SIDE_BY_SIDE)

    built_by_plan = {p: make_built_query(p, str(i)) for i, p in enumerate(plans)}
    result_by_built = {b: make_execution_result(Decimal(i)) for i, b in enumerate(built_by_plan.values())}

    planner.return_value = multi_plan
    builder.side_effect = built_by_plan.get
    executor.execute.side_effect = result_by_built.get
    merger.merge.return_value = MergedResult(
        columns=("m",), rows=(), row_count=0, merge_strategy=MergeStrategy.SIDE_BY_SIDE
    )

    orchestrator = AnalyticsQueryOrchestrator(planner, builder, executor, merger)
    orchestrator.execute(object())

    assert builder.call_count == 3
    assert executor.execute.call_count == 3
    called_plans = {call.args[0] for call in builder.call_args_list}
    assert called_plans == set(plans)


def test_multi_plan_result_propagated_correctly(fakes):
    planner, builder, executor, merger = fakes
    plan_a, plan_b = make_plan("v_sales"), make_plan("v_expenses")
    multi_plan = MultiQueryPlan(plans=(plan_a, plan_b), merge_strategy=MergeStrategy.COMPARE_METRICS)

    planner.return_value = multi_plan
    builder.side_effect = lambda p: make_built_query(p, p.source_view)
    executor.execute.side_effect = lambda bq: make_execution_result(Decimal("1"))
    merged = MergedResult(
        columns=("gross_sales", "total_expenses"),
        rows=({"gross_sales": Decimal("100"), "total_expenses": Decimal("60")},),
        row_count=1,
        merge_strategy=MergeStrategy.COMPARE_METRICS,
    )
    merger.merge.return_value = merged

    orchestrator = AnalyticsQueryOrchestrator(planner, builder, executor, merger)
    result = orchestrator.execute(object())

    assert result.columns == merged.columns
    assert result.rows == merged.rows
    assert result.row_count == merged.row_count
    assert result.merge_strategy is MergeStrategy.COMPARE_METRICS


# --------------------------------------------------------------------
# Correct plan/result association (no accidental cross-pairing)
# --------------------------------------------------------------------


def test_correct_plan_result_association_passed_to_merger(fakes):
    planner, builder, executor, merger = fakes
    plan_a = make_plan("v_sales")
    plan_b = make_plan("v_expenses")
    multi_plan = MultiQueryPlan(plans=(plan_a, plan_b), merge_strategy=MergeStrategy.SIDE_BY_SIDE)

    built_a = make_built_query(plan_a, "built-A")
    built_b = make_built_query(plan_b, "built-B")
    result_a = make_execution_result(Decimal("111"))
    result_b = make_execution_result(Decimal("222"))

    planner.return_value = multi_plan
    builder.side_effect = {plan_a: built_a, plan_b: built_b}.get
    executor.execute.side_effect = {built_a: result_a, built_b: result_b}.get
    merger.merge.return_value = MergedResult(
        columns=("m",), rows=(), row_count=0, merge_strategy=MergeStrategy.SIDE_BY_SIDE
    )

    orchestrator = AnalyticsQueryOrchestrator(planner, builder, executor, merger)
    orchestrator.execute(object())

    (called_multi_plan, called_executed_queries), _ = merger.merge.call_args
    assert called_multi_plan is multi_plan
    assert called_executed_queries == (
        ExecutedQuery(built_query=built_a, result=result_a),
        ExecutedQuery(built_query=built_b, result=result_b),
    )
    # Specifically: A's built_query must be paired with A's result, not B's.
    for eq in called_executed_queries:
        if eq.built_query is built_a:
            assert eq.result is result_a
        elif eq.built_query is built_b:
            assert eq.result is result_b
        else:
            pytest.fail("Unexpected built_query in merger input")


# --------------------------------------------------------------------
# Failure behavior
# --------------------------------------------------------------------


def test_planner_failure_stops_before_builder_and_executor(fakes):
    planner, builder, executor, merger = fakes
    planner.side_effect = RuntimeError("planning blew up")

    orchestrator = AnalyticsQueryOrchestrator(planner, builder, executor, merger)

    with pytest.raises(RuntimeError, match="planning blew up"):
        orchestrator.execute(object())

    builder.assert_not_called()
    executor.execute.assert_not_called()
    merger.merge.assert_not_called()


def test_builder_failure_on_second_plan_stops_before_merge(fakes):
    planner, builder, executor, merger = fakes
    plan_a, plan_b = make_plan("v_sales"), make_plan("v_expenses")
    multi_plan = MultiQueryPlan(plans=(plan_a, plan_b), merge_strategy=MergeStrategy.SIDE_BY_SIDE)
    built_a = make_built_query(plan_a, "A")

    planner.return_value = multi_plan

    def builder_side_effect(plan):
        if plan is plan_a:
            return built_a
        raise ValueError("bad plan for builder")

    builder.side_effect = builder_side_effect
    executor.execute.return_value = make_execution_result(Decimal("1"))

    orchestrator = AnalyticsQueryOrchestrator(planner, builder, executor, merger)

    with pytest.raises(ValueError, match="bad plan for builder"):
        orchestrator.execute(object())

    # plan_a's executor call already happened (sequential processing),
    # but plan_b never got past the builder, and the merger never ran.
    executor.execute.assert_called_once_with(built_a)
    merger.merge.assert_not_called()


def test_executor_failure_merger_not_called(fakes):
    planner, builder, executor, merger = fakes
    plan = make_plan("v_sales")
    built_query = make_built_query(plan, "A")

    planner.return_value = plan
    builder.return_value = built_query
    executor.execute.side_effect = ConnectionError("db unreachable")

    orchestrator = AnalyticsQueryOrchestrator(planner, builder, executor, merger)

    with pytest.raises(ConnectionError, match="db unreachable"):
        orchestrator.execute(object())

    merger.merge.assert_not_called()


def test_merger_failure_propagates(fakes):
    planner, builder, executor, merger = fakes
    plan_a, plan_b = make_plan("v_sales"), make_plan("v_expenses")
    multi_plan = MultiQueryPlan(plans=(plan_a, plan_b), merge_strategy=MergeStrategy.SIDE_BY_SIDE)

    planner.return_value = multi_plan
    builder.side_effect = lambda p: make_built_query(p, p.source_view)
    executor.execute.return_value = make_execution_result(Decimal("1"))
    merger.merge.side_effect = KeyError("duplicate merge key")

    orchestrator = AnalyticsQueryOrchestrator(planner, builder, executor, merger)

    with pytest.raises(KeyError, match="duplicate merge key"):
        orchestrator.execute(object())


# --------------------------------------------------------------------
# Dependency validation
# --------------------------------------------------------------------


@pytest.mark.parametrize("missing_index", [0, 1, 2, 3])
def test_missing_dependency_raises_at_construction(fakes, missing_index):
    deps = list(fakes)
    deps[missing_index] = None

    with pytest.raises(OrchestratorConfigurationError):
        AnalyticsQueryOrchestrator(*deps)


def test_invalid_plan_result_type_raises(fakes):
    planner, builder, executor, merger = fakes
    planner.return_value = "not a plan"

    orchestrator = AnalyticsQueryOrchestrator(planner, builder, executor, merger)

    with pytest.raises(InvalidPlanResultError):
        orchestrator.execute(object())

    builder.assert_not_called()