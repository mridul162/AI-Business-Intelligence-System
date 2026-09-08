from dataclasses import dataclass, field
from typing import Any

import pytest

from etl.analytics.planner.query_plan import MergeStrategy, MultiQueryPlan, QueryPlan
from etl.analytics.planner.query_planner import MetricDefinition, RegistryFilter, plan_query


# --------------------------------------------------------------------
# Tiny in-memory registry + request stand-ins for testing
# --------------------------------------------------------------------

REGISTRY = {
    "total_sales": MetricDefinition(
        name="total_sales", source_view="analytics.v_sales"
    ),
    "net_sales": MetricDefinition(
        name="net_sales", source_view="analytics.v_sales"
    ),
    "total_expenses": MetricDefinition(
        name="total_expenses", source_view="analytics.v_expenses"
    ),
    "cash_in": MetricDefinition(
        name="cash_in",
        source_view="analytics.v_cash_transactions",
        fixed_filters=(RegistryFilter("direction", "eq", "IN"),),
    ),
    "cash_out": MetricDefinition(
        name="cash_out",
        source_view="analytics.v_cash_transactions",
        fixed_filters=(RegistryFilter("direction", "eq", "OUT"),),
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
# Case A: same source, compatible (no) fixed filters -> one QueryPlan
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
        # fixed filter should have made it into the plan's filters
        assert any(f.field == "direction" for f in p.filters)


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
        time_grain="month",
    )

    result = plan_query(request, resolve_metric)

    assert isinstance(result, QueryPlan)
    assert result.metrics == ("total_sales",)
    assert result.dimensions == ("region",)
    assert result.time_grain == "month"


# --------------------------------------------------------------------
# Misc
# --------------------------------------------------------------------


def test_unknown_metric_raises():
    request = FakeRequest(metrics=("does_not_exist",))

    with pytest.raises(KeyError):
        plan_query(request, resolve_metric)


def test_empty_metrics_raises():
    request = FakeRequest(metrics=())

    with pytest.raises(ValueError):
        plan_query(request, resolve_metric)


def test_three_way_split_groups_correctly():
    """
    total_sales/net_sales (v_sales) should merge into one plan while
    cash_in/cash_out (v_cash_transactions, conflicting filters) stay
    split -- three metrics in, three groups... actually two groups for
    sales + two for cash = verifies grouping doesn't cross source
    views and doesn't over-merge within a source view when filters
    conflict.
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