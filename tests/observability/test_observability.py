from __future__ import annotations

import logging
from unittest.mock import Mock

from etl.analytics.executor.execution_models import ExecutionResult
from etl.analytics.merger.merge_models import MergedResult
from etl.analytics.orchestration.analytics_orchestrator import (
    AnalyticsQueryOrchestrator,
)
from etl.analytics.planner.query_plan import MultiQueryPlan, QueryPlan, MergeStrategy
from etl.analytics.sql.sql_models import BuiltQuery


def test_single_query_execution_logs_pipeline_stages(caplog):
    planner = Mock()
    builder = Mock()
    executor = Mock()
    merger = Mock()

    plan = Mock(spec=QueryPlan)
    built_query = Mock(spec=BuiltQuery)
    execution_result = ExecutionResult(
        columns=("metric",),
        rows=({"metric": 100},),
        row_count=1,
        duration_seconds=0.01,
    )

    planner.return_value = plan
    builder.return_value = built_query
    executor.execute.return_value = execution_result

    orchestrator = AnalyticsQueryOrchestrator(
        planner=planner,
        builder=builder,
        executor=executor,
        merger=merger,
    )

    with caplog.at_level(
        logging.INFO,
        logger="etl.analytics.orchestration.analytics_orchestrator",
    ):
        orchestrator.execute(Mock())

    messages = [record.message for record in caplog.records]

    assert any(
        "stage=planning" in message
        for message in messages
    )
    assert any(
        "stage=sql_building" in message
        for message in messages
    )
    assert any(
        "stage=database_execution" in message
        for message in messages
    )

    assert not any(
        "stage=result_merging" in message
        for message in messages
    )


def test_multi_query_execution_logs_each_plan_and_merge(caplog):
    planner = Mock()
    builder = Mock()
    executor = Mock()
    merger = Mock()

    plan_one = Mock(spec=QueryPlan)
    plan_two = Mock(spec=QueryPlan)
    multi_plan = Mock(spec=MultiQueryPlan)
    multi_plan.plans = (plan_one, plan_two)
    multi_plan.merge_strategy = MergeStrategy.SIDE_BY_SIDE

    built_query_one = Mock(spec=BuiltQuery)
    built_query_two = Mock(spec=BuiltQuery)

    execution_result_one = ExecutionResult(
        columns=("metric_a",),
        rows=({"metric_a": 100},),
        row_count=1,
        duration_seconds=0.01,
    )

    execution_result_two = ExecutionResult(
        columns=("metric_b",),
        rows=({"metric_b": 200},),
        row_count=1,
        duration_seconds=0.01,
    )

    merged_result = MergedResult(
        columns=("metric_a", "metric_b"),
        rows=(
            {
                "metric_a": 100,
                "metric_b": 200,
            },
        ),
        row_count=1,
        merge_strategy=multi_plan.merge_strategy,
    )

    planner.return_value = multi_plan

    builder.side_effect = [
        built_query_one,
        built_query_two,
    ]

    executor.execute.side_effect = [
        execution_result_one,
        execution_result_two,
    ]

    merger.merge.return_value = merged_result

    orchestrator = AnalyticsQueryOrchestrator(
        planner=planner,
        builder=builder,
        executor=executor,
        merger=merger,
    )

    with caplog.at_level(
        logging.INFO,
        logger="etl.analytics.orchestration.analytics_orchestrator",
    ):
        orchestrator.execute(Mock())

    messages = [record.message for record in caplog.records]

    assert any(
        "stage=planning" in message
        for message in messages
    )

    sql_building_messages = [
        message
        for message in messages
        if "stage=sql_building" in message
    ]

    database_execution_messages = [
        message
        for message in messages
        if "stage=database_execution" in message
    ]

    assert len(sql_building_messages) == 2
    assert len(database_execution_messages) == 2

    assert any(
        "stage=result_merging" in message
        for message in messages
    )

    assert any(
        "plan_index=0" in message
        for message in sql_building_messages
    )
    assert any(
        "plan_index=1" in message
        for message in sql_building_messages
    )

    assert any(
        "plan_index=0" in message
        for message in database_execution_messages
    )
    assert any(
        "plan_index=1" in message
        for message in database_execution_messages
    )