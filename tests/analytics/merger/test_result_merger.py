from datetime import date
from decimal import Decimal

import pytest

from etl.analytics.executor.execution_models import ExecutionResult
from etl.analytics.merger import (
    DuplicateMergeKeyError,
    ExecutedQuery,
    IncompatibleGroupingError,
    InvalidMergeInputError,
    MissingResultColumnError,
    ResultMerger,
    ResultPlanMismatchError,
)
from etl.analytics.planner.query_plan import MergeStrategy, MultiQueryPlan, QueryPlan
from etl.analytics.sql.sql_models import BuiltQuery


def make_plan(source_view: str, metrics: tuple[str, ...], **kwargs) -> QueryPlan:
    return QueryPlan(source_view=source_view, metrics=metrics, **kwargs)


def make_executed(
    plan: QueryPlan,
    metric_output_fields: tuple[str, ...],
    dimension_fields: tuple[str, ...] = (),
    time_bucket_alias: str | None = None,
    columns: tuple[str, ...] | None = None,
    rows: tuple[dict, ...] = (),
) -> ExecutedQuery:
    built_query = BuiltQuery(
        statement=None,  # never touched by the merger # type: ignore
        plan=plan,
        metric_output_fields=metric_output_fields,
        dimension_fields=dimension_fields,
        time_bucket_alias=time_bucket_alias,
    )
    if columns is None:
        columns = dimension_fields + ((time_bucket_alias,) if time_bucket_alias else ()) + metric_output_fields
    result = ExecutionResult(
        columns=columns,
        rows=rows,
        row_count=len(rows),
        duration_seconds=0.001,
    )
    return ExecutedQuery(built_query=built_query, result=result)


# --------------------------------------------------------------------
# Basic: scalar (no grouping) results
# --------------------------------------------------------------------


def test_two_scalar_results_merge():
    plan_a = make_plan("v_sales", ("gross_sales",))
    plan_b = make_plan("v_expenses", ("total_expenses",))
    multi_plan = MultiQueryPlan(plans=(plan_a, plan_b), merge_strategy=MergeStrategy.SIDE_BY_SIDE)

    eq_a = make_executed(plan_a, ("gross_sales",), rows=({"gross_sales": Decimal("100")},))
    eq_b = make_executed(plan_b, ("total_expenses",), rows=({"total_expenses": Decimal("60")},))

    merged = ResultMerger().merge(multi_plan, (eq_a, eq_b))

    assert merged.columns == ("gross_sales", "total_expenses")
    assert merged.rows == ({"gross_sales": Decimal("100"), "total_expenses": Decimal("60")},)
    assert merged.row_count == 1
    assert merged.merge_strategy is MergeStrategy.SIDE_BY_SIDE


def test_three_scalar_results_merge():
    plans = [
        make_plan("v_sales", ("gross_sales",)),
        make_plan("v_expenses", ("total_expenses",)),
        make_plan("v_payments", ("total_payments",)),
    ]
    multi_plan = MultiQueryPlan(plans=tuple(plans), merge_strategy=MergeStrategy.SIDE_BY_SIDE)
    eqs = (
        make_executed(plans[0], ("gross_sales",), rows=({"gross_sales": Decimal("100")},)),
        make_executed(plans[1], ("total_expenses",), rows=({"total_expenses": Decimal("60")},)),
        make_executed(plans[2], ("total_payments",), rows=({"total_payments": Decimal("40")},)),
    )

    merged = ResultMerger().merge(multi_plan, eqs)

    assert merged.rows == (
        {"gross_sales": Decimal("100"), "total_expenses": Decimal("60"), "total_payments": Decimal("40")},
    )


# --------------------------------------------------------------------
# Grouped results: one dimension, multiple dimensions, time bucket
# --------------------------------------------------------------------


def test_merge_by_one_dimension_single_row():
    plan_a = make_plan("v_sales", ("gross_sales",), dimensions=("product_category",))
    plan_b = make_plan("v_expenses", ("total_expenses",), dimensions=("product_category",))
    multi_plan = MultiQueryPlan(plans=(plan_a, plan_b), merge_strategy=MergeStrategy.COMPARE_METRICS)

    eq_a = make_executed(
        plan_a, ("gross_sales",), dimension_fields=("product_category",),
        rows=({"product_category": "Nuts", "gross_sales": Decimal("100")},),
    )
    eq_b = make_executed(
        plan_b, ("total_expenses",), dimension_fields=("product_category",),
        rows=({"product_category": "Nuts", "total_expenses": Decimal("40")},),
    )

    merged = ResultMerger().merge(multi_plan, (eq_a, eq_b))

    assert merged.rows == (
        {"product_category": "Nuts", "gross_sales": Decimal("100"), "total_expenses": Decimal("40")},
    )


def test_merge_by_one_dimension_multiple_rows():
    plan_a = make_plan("v_sales", ("gross_sales",), dimensions=("product_category",))
    plan_b = make_plan("v_expenses", ("total_expenses",), dimensions=("product_category",))
    multi_plan = MultiQueryPlan(plans=(plan_a, plan_b), merge_strategy=MergeStrategy.COMPARE_METRICS)

    eq_a = make_executed(
        plan_a, ("gross_sales",), dimension_fields=("product_category",),
        rows=(
            {"product_category": "Nuts", "gross_sales": Decimal("100")},
            {"product_category": "Snacks", "gross_sales": Decimal("200")},
        ),
    )
    eq_b = make_executed(
        plan_b, ("total_expenses",), dimension_fields=("product_category",),
        rows=(
            {"product_category": "Nuts", "total_expenses": Decimal("40")},
            {"product_category": "Snacks", "total_expenses": Decimal("90")},
        ),
    )

    merged = ResultMerger().merge(multi_plan, (eq_a, eq_b))

    by_category = {r["product_category"]: r for r in merged.rows}
    assert by_category["Nuts"]["total_expenses"] == Decimal("40")
    assert by_category["Snacks"]["gross_sales"] == Decimal("200")
    assert merged.row_count == 2


def test_merge_by_multiple_dimensions():
    dims = ("location_name", "product_category")
    plan_a = make_plan("v_sales", ("gross_sales",), dimensions=dims)
    plan_b = make_plan("v_payments", ("total_payments",), dimensions=dims)
    multi_plan = MultiQueryPlan(plans=(plan_a, plan_b), merge_strategy=MergeStrategy.SIDE_BY_SIDE)

    eq_a = make_executed(
        plan_a, ("gross_sales",), dimension_fields=dims,
        rows=({"location_name": "Main", "product_category": "Nuts", "gross_sales": Decimal("10")},),
    )
    eq_b = make_executed(
        plan_b, ("total_payments",), dimension_fields=dims,
        rows=({"location_name": "Main", "product_category": "Nuts", "total_payments": Decimal("5")},),
    )

    merged = ResultMerger().merge(multi_plan, (eq_a, eq_b))

    assert merged.rows == (
        {
            "location_name": "Main",
            "product_category": "Nuts",
            "gross_sales": Decimal("10"),
            "total_payments": Decimal("5"),
        },
    )


def test_merge_by_time_bucket():
    plan_a = make_plan("v_cash_transactions", ("cash_in",), time_grain="monthly")
    plan_b = make_plan("v_cash_transactions", ("cash_out",), time_grain="monthly")
    multi_plan = MultiQueryPlan(plans=(plan_a, plan_b), merge_strategy=MergeStrategy.SPLIT_METRICS)

    eq_a = make_executed(
        plan_a, ("cash_in",), time_bucket_alias="period",
        rows=(
            {"period": date(2026, 1, 1), "cash_in": Decimal("10000")},
            {"period": date(2026, 2, 1), "cash_in": Decimal("12000")},
        ),
    )
    eq_b = make_executed(
        plan_b, ("cash_out",), time_bucket_alias="period",
        rows=(
            {"period": date(2026, 1, 1), "cash_out": Decimal("7000")},
            {"period": date(2026, 2, 1), "cash_out": Decimal("9000")},
        ),
    )

    merged = ResultMerger().merge(multi_plan, (eq_a, eq_b))

    by_period = {r["period"]: r for r in merged.rows}
    assert by_period[date(2026, 1, 1)] == {
        "period": date(2026, 1, 1), "cash_in": Decimal("10000"), "cash_out": Decimal("7000"),
    }
    assert by_period[date(2026, 2, 1)]["cash_out"] == Decimal("9000")


def test_merge_by_dimension_and_time_bucket():
    plan_a = make_plan(
        "v_sales", ("gross_sales",), dimensions=("product_category",), time_grain="monthly"
    )
    plan_b = make_plan(
        "v_expenses", ("total_expenses",), dimensions=("product_category",), time_grain="monthly"
    )
    multi_plan = MultiQueryPlan(plans=(plan_a, plan_b), merge_strategy=MergeStrategy.COMPARE_METRICS)

    eq_a = make_executed(
        plan_a, ("gross_sales",), dimension_fields=("product_category",), time_bucket_alias="period",
        rows=({"product_category": "Nuts", "period": date(2026, 1, 1), "gross_sales": Decimal("10")},),
    )
    eq_b = make_executed(
        plan_b, ("total_expenses",), dimension_fields=("product_category",), time_bucket_alias="period",
        rows=({"product_category": "Nuts", "period": date(2026, 1, 1), "total_expenses": Decimal("4")},),
    )

    merged = ResultMerger().merge(multi_plan, (eq_a, eq_b))

    assert merged.rows == (
        {
            "product_category": "Nuts",
            "period": date(2026, 1, 1),
            "gross_sales": Decimal("10"),
            "total_expenses": Decimal("4"),
        },
    )


# --------------------------------------------------------------------
# Missing keys -> 0, not skipped, not summed
# --------------------------------------------------------------------


def test_key_missing_from_second_query_fills_zero():
    plan_a = make_plan("v_cash_transactions", ("cash_in",), time_grain="monthly")
    plan_b = make_plan("v_cash_transactions", ("cash_out",), time_grain="monthly")
    multi_plan = MultiQueryPlan(plans=(plan_a, plan_b), merge_strategy=MergeStrategy.SPLIT_METRICS)

    eq_a = make_executed(
        plan_a, ("cash_in",), time_bucket_alias="period",
        rows=(
            {"period": date(2026, 1, 1), "cash_in": Decimal("1000")},
            {"period": date(2026, 2, 1), "cash_in": Decimal("1200")},
        ),
    )
    eq_b = make_executed(
        plan_b, ("cash_out",), time_bucket_alias="period",
        rows=({"period": date(2026, 1, 1), "cash_out": Decimal("800")},),  # no Feb row
    )

    merged = ResultMerger().merge(multi_plan, (eq_a, eq_b))

    by_period = {r["period"]: r for r in merged.rows}
    assert by_period[date(2026, 2, 1)]["cash_out"] == 0
    assert by_period[date(2026, 1, 1)]["cash_out"] == Decimal("800")


def test_key_missing_from_first_query_fills_zero():
    plan_a = make_plan("v_cash_transactions", ("cash_in",), time_grain="monthly")
    plan_b = make_plan("v_cash_transactions", ("cash_out",), time_grain="monthly")
    multi_plan = MultiQueryPlan(plans=(plan_a, plan_b), merge_strategy=MergeStrategy.SPLIT_METRICS)

    eq_a = make_executed(
        plan_a, ("cash_in",), time_bucket_alias="period",
        rows=({"period": date(2026, 1, 1), "cash_in": Decimal("1000")},),  # no March row
    )
    eq_b = make_executed(
        plan_b, ("cash_out",), time_bucket_alias="period",
        rows=(
            {"period": date(2026, 1, 1), "cash_out": Decimal("800")},
            {"period": date(2026, 3, 1), "cash_out": Decimal("700")},
        ),
    )

    merged = ResultMerger().merge(multi_plan, (eq_a, eq_b))

    by_period = {r["period"]: r for r in merged.rows}
    assert by_period[date(2026, 3, 1)]["cash_in"] == 0
    assert by_period[date(2026, 3, 1)]["cash_out"] == Decimal("700")


def test_key_present_in_all_queries():
    plan_a = make_plan("v_cash_transactions", ("cash_in",), time_grain="monthly")
    plan_b = make_plan("v_cash_transactions", ("cash_out",), time_grain="monthly")
    multi_plan = MultiQueryPlan(plans=(plan_a, plan_b), merge_strategy=MergeStrategy.SPLIT_METRICS)

    eq_a = make_executed(
        plan_a, ("cash_in",), time_bucket_alias="period",
        rows=({"period": date(2026, 1, 1), "cash_in": Decimal("1000")},),
    )
    eq_b = make_executed(
        plan_b, ("cash_out",), time_bucket_alias="period",
        rows=({"period": date(2026, 1, 1), "cash_out": Decimal("800")},),
    )

    merged = ResultMerger().merge(multi_plan, (eq_a, eq_b))

    assert merged.rows == ({"period": date(2026, 1, 1), "cash_in": Decimal("1000"), "cash_out": Decimal("800")},)


# --------------------------------------------------------------------
# Empty results
# --------------------------------------------------------------------


def test_one_query_empty_other_has_rows():
    plan_a = make_plan("v_sales", ("gross_sales",), dimensions=("product_category",))
    plan_b = make_plan("v_expenses", ("total_expenses",), dimensions=("product_category",))
    multi_plan = MultiQueryPlan(plans=(plan_a, plan_b), merge_strategy=MergeStrategy.COMPARE_METRICS)

    eq_a = make_executed(
        plan_a, ("gross_sales",), dimension_fields=("product_category",),
        rows=({"product_category": "Nuts", "gross_sales": Decimal("100")},),
    )
    eq_b = make_executed(plan_b, ("total_expenses",), dimension_fields=("product_category",), rows=())

    merged = ResultMerger().merge(multi_plan, (eq_a, eq_b))

    assert merged.rows == ({"product_category": "Nuts", "gross_sales": Decimal("100"), "total_expenses": 0},)


def test_multiple_queries_empty_one_has_rows():
    plans = [
        make_plan("v_sales", ("gross_sales",)),
        make_plan("v_expenses", ("total_expenses",)),
        make_plan("v_payments", ("total_payments",)),
    ]
    multi_plan = MultiQueryPlan(plans=tuple(plans), merge_strategy=MergeStrategy.SIDE_BY_SIDE)
    eqs = (
        make_executed(plans[0], ("gross_sales",), rows=({"gross_sales": Decimal("100")},)),
        make_executed(plans[1], ("total_expenses",), rows=()),
        make_executed(plans[2], ("total_payments",), rows=()),
    )

    merged = ResultMerger().merge(multi_plan, eqs)

    assert merged.rows == ({"gross_sales": Decimal("100"), "total_expenses": 0, "total_payments": 0},)


def test_all_queries_empty():
    plan_a = make_plan("v_sales", ("gross_sales",))
    plan_b = make_plan("v_expenses", ("total_expenses",))
    multi_plan = MultiQueryPlan(plans=(plan_a, plan_b), merge_strategy=MergeStrategy.SIDE_BY_SIDE)

    eq_a = make_executed(plan_a, ("gross_sales",), rows=())
    eq_b = make_executed(plan_b, ("total_expenses",), rows=())

    merged = ResultMerger().merge(multi_plan, (eq_a, eq_b))

    assert merged.rows == ()
    assert merged.row_count == 0
    assert merged.columns == ("gross_sales", "total_expenses")


# --------------------------------------------------------------------
# Errors
# --------------------------------------------------------------------


def test_wrong_number_of_execution_results_raises():
    plan_a = make_plan("v_sales", ("gross_sales",))
    plan_b = make_plan("v_expenses", ("total_expenses",))
    multi_plan = MultiQueryPlan(plans=(plan_a, plan_b), merge_strategy=MergeStrategy.SIDE_BY_SIDE)
    eq_a = make_executed(plan_a, ("gross_sales",), rows=({"gross_sales": Decimal("1")},))

    with pytest.raises(InvalidMergeInputError):
        ResultMerger().merge(multi_plan, (eq_a,))


def test_missing_metric_column_raises():
    plan_a = make_plan("v_sales", ("gross_sales",))
    plan_b = make_plan("v_expenses", ("total_expenses",))
    multi_plan = MultiQueryPlan(plans=(plan_a, plan_b), merge_strategy=MergeStrategy.SIDE_BY_SIDE)

    eq_a = make_executed(plan_a, ("gross_sales",), rows=({"gross_sales": Decimal("1")},))
    # eq_b claims metric_output_fields=("total_expenses",) but its result
    # columns don't actually include it.
    eq_b = make_executed(
        plan_b, ("total_expenses",), columns=(), rows=({},)
    )

    with pytest.raises(MissingResultColumnError):
        ResultMerger().merge(multi_plan, (eq_a, eq_b))


def test_missing_dimension_column_raises():
    plan_a = make_plan("v_sales", ("gross_sales",), dimensions=("product_category",))
    multi_plan_plan_b = make_plan("v_expenses", ("total_expenses",), dimensions=("product_category",))
    multi_plan = MultiQueryPlan(
        plans=(plan_a, multi_plan_plan_b), merge_strategy=MergeStrategy.COMPARE_METRICS
    )

    eq_a = make_executed(
        plan_a, ("gross_sales",), dimension_fields=("product_category",), columns=("gross_sales",),
        rows=({"gross_sales": Decimal("1")},),  # missing product_category column
    )
    eq_b = make_executed(
        multi_plan_plan_b, ("total_expenses",), dimension_fields=("product_category",),
        rows=({"product_category": "Nuts", "total_expenses": Decimal("1")},),
    )

    with pytest.raises(MissingResultColumnError):
        ResultMerger().merge(multi_plan, (eq_a, eq_b))


def test_missing_time_bucket_column_raises():
    plan_a = make_plan("v_cash_transactions", ("cash_in",), time_grain="monthly")
    plan_b = make_plan("v_cash_transactions", ("cash_out",), time_grain="monthly")
    multi_plan = MultiQueryPlan(plans=(plan_a, plan_b), merge_strategy=MergeStrategy.SPLIT_METRICS)

    eq_a = make_executed(
        plan_a, ("cash_in",), time_bucket_alias="period", columns=("cash_in",),
        rows=({"cash_in": Decimal("1")},),  # missing period column
    )
    eq_b = make_executed(
        plan_b, ("cash_out",), time_bucket_alias="period",
        rows=({"period": date(2026, 1, 1), "cash_out": Decimal("1")},),
    )

    with pytest.raises(MissingResultColumnError):
        ResultMerger().merge(multi_plan, (eq_a, eq_b))


def test_duplicate_merge_key_raises():
    plan_a = make_plan("v_sales", ("gross_sales",), dimensions=("product_category",))
    plan_b = make_plan("v_expenses", ("total_expenses",), dimensions=("product_category",))
    multi_plan = MultiQueryPlan(plans=(plan_a, plan_b), merge_strategy=MergeStrategy.COMPARE_METRICS)

    eq_a = make_executed(
        plan_a, ("gross_sales",), dimension_fields=("product_category",),
        rows=(
            {"product_category": "Nuts", "gross_sales": Decimal("1")},
            {"product_category": "Nuts", "gross_sales": Decimal("2")},
        ),
    )
    eq_b = make_executed(
        plan_b, ("total_expenses",), dimension_fields=("product_category",),
        rows=({"product_category": "Nuts", "total_expenses": Decimal("1")},),
    )

    with pytest.raises(DuplicateMergeKeyError):
        ResultMerger().merge(multi_plan, (eq_a, eq_b))


def test_incompatible_grouping_raises():
    plan_a = make_plan("v_sales", ("gross_sales",), dimensions=("product_category",))
    plan_b = make_plan("v_expenses", ("total_expenses",), dimensions=("location_name",))
    multi_plan = MultiQueryPlan(plans=(plan_a, plan_b), merge_strategy=MergeStrategy.COMPARE_METRICS)

    eq_a = make_executed(
        plan_a, ("gross_sales",), dimension_fields=("product_category",),
        rows=({"product_category": "Nuts", "gross_sales": Decimal("1")},),
    )
    eq_b = make_executed(
        plan_b, ("total_expenses",), dimension_fields=("location_name",),
        rows=({"location_name": "Main", "total_expenses": Decimal("1")},),
    )

    with pytest.raises(IncompatibleGroupingError):
        ResultMerger().merge(multi_plan, (eq_a, eq_b))


def test_executed_query_not_matching_any_plan_raises():
    plan_a = make_plan("v_sales", ("gross_sales",))
    plan_b = make_plan("v_expenses", ("total_expenses",))
    unrelated_plan = make_plan("v_payments", ("total_payments",))
    multi_plan = MultiQueryPlan(plans=(plan_a, plan_b), merge_strategy=MergeStrategy.SIDE_BY_SIDE)

    eq_a = make_executed(plan_a, ("gross_sales",), rows=({"gross_sales": Decimal("1")},))
    eq_unrelated = make_executed(unrelated_plan, ("total_payments",), rows=({"total_payments": Decimal("1")},))

    with pytest.raises(ResultPlanMismatchError):
        ResultMerger().merge(multi_plan, (eq_a, eq_unrelated))


def test_colliding_metric_output_fields_raises():
    # Contrived, but validates the merger refuses to silently overwrite
    # one metric's values with another's under the same column name.
    plan_a = make_plan("v_sales", ("gross_sales",))
    plan_b = make_plan("v_expenses", ("gross_sales",))  # same output field name
    multi_plan = MultiQueryPlan(plans=(plan_a, plan_b), merge_strategy=MergeStrategy.SIDE_BY_SIDE)

    eq_a = make_executed(plan_a, ("gross_sales",), rows=({"gross_sales": Decimal("1")},))
    eq_b = make_executed(plan_b, ("gross_sales",), rows=({"gross_sales": Decimal("2")},))

    with pytest.raises(InvalidMergeInputError):
        ResultMerger().merge(multi_plan, (eq_a, eq_b))


# --------------------------------------------------------------------
# Strategies pass through unchanged
# --------------------------------------------------------------------


@pytest.mark.parametrize(
    "strategy",
    [MergeStrategy.SPLIT_METRICS, MergeStrategy.COMPARE_METRICS, MergeStrategy.SIDE_BY_SIDE],
)
def test_merge_strategy_is_recorded_not_reinterpreted(strategy):
    plan_a = make_plan("v_sales", ("gross_sales",))
    plan_b = make_plan("v_expenses", ("total_expenses",))
    multi_plan = MultiQueryPlan(plans=(plan_a, plan_b), merge_strategy=strategy)

    eq_a = make_executed(plan_a, ("gross_sales",), rows=({"gross_sales": Decimal("1")},))
    eq_b = make_executed(plan_b, ("total_expenses",), rows=({"total_expenses": Decimal("2")},))

    merged = ResultMerger().merge(multi_plan, (eq_a, eq_b))

    assert merged.merge_strategy is strategy
    # No derived arithmetic anywhere -- exactly the two source values.
    assert merged.rows == ({"gross_sales": Decimal("1"), "total_expenses": Decimal("2")},)


# --------------------------------------------------------------------
# Data preservation
# --------------------------------------------------------------------


def test_preserves_decimal():
    plan_a = make_plan("v_sales", ("gross_sales",))
    plan_b = make_plan("v_expenses", ("total_expenses",))
    multi_plan = MultiQueryPlan(plans=(plan_a, plan_b), merge_strategy=MergeStrategy.SIDE_BY_SIDE)

    eq_a = make_executed(plan_a, ("gross_sales",), rows=({"gross_sales": Decimal("123.45")},))
    eq_b = make_executed(plan_b, ("total_expenses",), rows=({"total_expenses": Decimal("67.89")},))

    merged = ResultMerger().merge(multi_plan, (eq_a, eq_b))

    row = merged.rows[0]
    assert isinstance(row["gross_sales"], Decimal)
    assert row["gross_sales"] == Decimal("123.45")


def test_preserves_dates():
    plan_a = make_plan("v_cash_transactions", ("cash_in",), time_grain="monthly")
    plan_b = make_plan("v_cash_transactions", ("cash_out",), time_grain="monthly")
    multi_plan = MultiQueryPlan(plans=(plan_a, plan_b), merge_strategy=MergeStrategy.SPLIT_METRICS)

    eq_a = make_executed(
        plan_a, ("cash_in",), time_bucket_alias="period",
        rows=({"period": date(2026, 5, 1), "cash_in": Decimal("1")},),
    )
    eq_b = make_executed(
        plan_b, ("cash_out",), time_bucket_alias="period",
        rows=({"period": date(2026, 5, 1), "cash_out": Decimal("2")},),
    )

    merged = ResultMerger().merge(multi_plan, (eq_a, eq_b))

    assert isinstance(merged.rows[0]["period"], date)
    assert merged.rows[0]["period"] == date(2026, 5, 1)


def test_preserves_explicit_none_distinct_from_missing_key():
    plan_a = make_plan("v_sales", ("gross_sales",), dimensions=("product_category",))
    plan_b = make_plan("v_expenses", ("total_expenses",), dimensions=("product_category",))
    multi_plan = MultiQueryPlan(plans=(plan_a, plan_b), merge_strategy=MergeStrategy.COMPARE_METRICS)

    # Nuts: row exists but the aggregate itself is NULL -> stays None.
    # Snacks: row exists only in eq_a -> eq_b's metric is 0, not None.
    eq_a = make_executed(
        plan_a, ("gross_sales",), dimension_fields=("product_category",),
        rows=(
            {"product_category": "Nuts", "gross_sales": None},
            {"product_category": "Snacks", "gross_sales": Decimal("50")},
        ),
    )
    eq_b = make_executed(
        plan_b, ("total_expenses",), dimension_fields=("product_category",),
        rows=({"product_category": "Nuts", "total_expenses": Decimal("10")},),
    )

    merged = ResultMerger().merge(multi_plan, (eq_a, eq_b))

    by_category = {r["product_category"]: r for r in merged.rows}
    assert by_category["Nuts"]["gross_sales"] is None
    assert by_category["Snacks"]["total_expenses"] == 0