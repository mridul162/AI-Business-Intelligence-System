from dataclasses import dataclass
from typing import Any

import pytest

from etl.analytics.metrics.definitions import MetricDefinition
from etl.analytics.planner.query_plan import MergeStrategy, MultiQueryPlan, QueryPlan
from etl.analytics.planner.query_planner import UnknownMetricError, plan_query
from etl.analytics.schemas import AnalyticalQueryRequest, FilterCondition


# --------------------------------------------------------------------
# Tiny in-memory registry + request stand-ins for testing
# --------------------------------------------------------------------


def make_metric(
    name: str,
    source_view: str,
    filters: tuple[str, ...] = (),
    supported_dimensions: tuple[str, ...] = (),
    supported_time_grains: tuple[str, ...] = (
        "daily", "weekly", "monthly", "quarterly", "yearly",
    ),
) -> MetricDefinition:
    """Build a minimal-but-real MetricDefinition for planner tests."""
    return MetricDefinition(
        name=name,
        display_name=name,
        description=name,
        source_view=source_view,
        aggregation="sum",
        expression=f"SUM({name})",
        filters=filters,
        supported_dimensions=supported_dimensions,
        supported_time_grains=supported_time_grains, # type: ignore
        output_field=name,
    )


REGISTRY = {
    "total_sales": make_metric("total_sales", "analytics.v_sales"),
    "net_sales": make_metric("net_sales", "analytics.v_sales"),
    "total_expenses": make_metric("total_expenses", "analytics.v_expenses"),
    "cash_in": make_metric(
        "cash_in", "analytics.v_cash_transactions", filters=("direction = 'IN'",)
    ),
    "cash_out": make_metric(
        "cash_out", "analytics.v_cash_transactions", filters=("direction = 'OUT'",)
    ),
}


def resolve_metric(name: str) -> MetricDefinition:
    return REGISTRY[name]


@dataclass
class FakeRequest:
    metrics: tuple[str, ...]
    dimensions: tuple[str, ...] = ()
    filters: tuple[Any, ...] = ()
    time_range: Any = None
    time_grain: str | None = None
    sort_by: str | None = None
    sort_order: str | None = None
    limit: int | None = None
    comparison: bool = False


# --------------------------------------------------------------------
# Case A: same source, identical (no) fixed filters -> one QueryPlan
# --------------------------------------------------------------------


def test_case_a_same_source_merges_into_one_plan():
    request = FakeRequest(metrics=("total_sales", "net_sales"))

    result = plan_query(request, resolve_metric)

    assert isinstance(result, QueryPlan)
    assert result.source_view == "analytics.v_sales"
    assert set(result.metrics) == {"total_sales", "net_sales"}


# --------------------------------------------------------------------
# Case B: same source, conflicting fixed filters -> SPLIT_METRICS
# --------------------------------------------------------------------


def test_case_b_conflicting_fixed_filters_split():
    request = FakeRequest(metrics=("cash_in", "cash_out"))

    result = plan_query(request, resolve_metric)

    assert isinstance(result, MultiQueryPlan)
    assert result.merge_strategy is MergeStrategy.SPLIT_METRICS
    assert len(result.plans) == 2
    assert {p.metrics[0] for p in result.plans} == {"cash_in", "cash_out"}
    for p in result.plans:
        assert p.source_view == "analytics.v_cash_transactions"
        # Registry fixed filters are NOT injected into QueryPlan.filters
        # (the SQL Builder pulls them from the registry itself) -- only
        # user-requested filters live here, and this request had none.
        assert p.filters == ()


# --------------------------------------------------------------------
# Case C: different source views, no comparison framing -> SIDE_BY_SIDE
# --------------------------------------------------------------------


def test_case_c_different_sources_side_by_side_by_default():
    request = FakeRequest(metrics=("total_sales", "total_expenses"))

    result = plan_query(request, resolve_metric)

    assert isinstance(result, MultiQueryPlan)
    assert result.merge_strategy is MergeStrategy.SIDE_BY_SIDE
    assert len(result.plans) == 2


def test_case_c_different_sources_compare_when_flagged():
    request = FakeRequest(
        metrics=("total_sales", "total_expenses"), comparison=True
    )

    result = plan_query(request, resolve_metric)

    assert isinstance(result, MultiQueryPlan)
    assert result.merge_strategy is MergeStrategy.COMPARE_METRICS


# --------------------------------------------------------------------
# Case D: single metric with dimensions/time_grain -> one QueryPlan
# --------------------------------------------------------------------


def test_case_d_single_metric_by_month():
    request = FakeRequest(
        metrics=("total_sales",),
        dimensions=("region",),
        time_grain="monthly",
    )

    result = plan_query(request, resolve_metric)

    assert isinstance(result, QueryPlan)
    assert result.metrics == ("total_sales",)
    assert result.dimensions == ("region",)
    assert result.time_grain == "monthly"


# --------------------------------------------------------------------
# User filters ARE carried through
# --------------------------------------------------------------------


def test_user_filters_pass_through_to_query_plan():
    from etl.analytics.planner.query_plan import PlanFilter

    user_filter = PlanFilter(field="region", operator="eq", value="West")
    request = FakeRequest(metrics=("total_sales",), filters=(user_filter,))

    result = plan_query(request, resolve_metric)

    assert isinstance(result, QueryPlan)
    assert result.filters == (user_filter,)


def test_phase_9_request_is_normalized_for_planning():
    request = AnalyticalQueryRequest(
        metric="total_sales",
        additional_metrics=("net_sales",),
        filters=(FilterCondition("region", "eq", "West"),),
    )

    result = plan_query(request, resolve_metric)

    assert isinstance(result, QueryPlan)
    assert result.metrics == ("total_sales", "net_sales")
    assert result.filters[0].field == "region"
    assert result.filters[0].operator == "eq"
    assert result.filters[0].value == "West"


# --------------------------------------------------------------------
# Misc
# --------------------------------------------------------------------


def test_unknown_metric_raises():
    request = FakeRequest(metrics=("does_not_exist",))

    with pytest.raises(UnknownMetricError):
        plan_query(request, resolve_metric)


def test_empty_metrics_raises():
    request = FakeRequest(metrics=())

    with pytest.raises(ValueError):
        plan_query(request, resolve_metric)


def test_three_way_split_groups_correctly():
    """
    total_sales/net_sales (v_sales) should merge into one plan while
    cash_in/cash_out (v_cash_transactions, conflicting filters) stay
    split -- verifies grouping doesn't cross source views and doesn't
    over-merge within a source view when fixed filters conflict.
    """
    request = FakeRequest(
        metrics=("total_sales", "net_sales", "cash_in", "cash_out")
    )

    result = plan_query(request, resolve_metric)

    assert isinstance(result, MultiQueryPlan)
    assert len(result.plans) == 3  # {sales}, {cash_in}, {cash_out}
    sales_plan = next(
        p for p in result.plans if p.source_view == "analytics.v_sales"
    )
    assert set(sales_plan.metrics) == {"total_sales", "net_sales"}