"""
Phase 8.4 — Query builder tests.

Covers the roadmap's:
  - Aggregation correctness
  - Dimension filtering
  - Time filtering (grains + custom date range)
  - Grouping (single/multi dimension, +time)
  - Edge cases: ratio metrics, mismatched expression/aggregation,
    unknown time grains, SQL-injection-shaped input

Assertions check the *shape* of the generated SQL/params rather than
byte-for-byte strings, so formatting changes in builder.py don't
make these tests brittle for no reason — but every caller-supplied
value is checked to land in `params`, never spliced into `sql`.
"""

from __future__ import annotations

import unittest
from datetime import date

from etl.analytics.metrics.definitions import MetricDefinition
from etl.analytics.metrics.registry import METRIC_REGISTRY
from etl.analytics.query.builder import BuildError, build_query
from etl.analytics.query.models import FilterOperator, OrderBy, QueryFilter, QueryRequest
from etl.analytics.query.time_grains import date_trunc_expression
from etl.analytics.query.validator import ValidationError


class TestAggregationCorrectness(unittest.TestCase):
    def test_sum_metric(self) -> None:
        compiled = build_query(QueryRequest(metrics=("gross_sales",)))
        self.assertIn("SUM(gross_sales)", compiled.sql)

    def test_count_distinct_metric(self) -> None:
        compiled = build_query(QueryRequest(metrics=("total_orders",)))
        self.assertIn("COUNT(DISTINCT order_id)", compiled.sql)

    def test_conditional_aggregation_for_metrics_with_builtin_filters(self) -> None:
        # cash_in and cash_out share a view but need different CASE WHEN
        # guards so they can be selected side by side.
        compiled = build_query(QueryRequest(metrics=("cash_in", "cash_out")))
        self.assertIn("CASE WHEN direction = 'IN' THEN amount ELSE NULL END", compiled.sql)
        self.assertIn("CASE WHEN direction = 'OUT' THEN amount ELSE NULL END", compiled.sql)
        self.assertIn("AS cash_in", compiled.sql)
        self.assertIn("AS cash_out", compiled.sql)

    def test_partner_capital_in_out_use_transaction_type_not_direction(self) -> None:
        compiled = build_query(
            QueryRequest(metrics=("partner_capital_in", "partner_capital_out"))
        )
        self.assertIn("transaction_type = 'CAPITAL'", compiled.sql)
        self.assertIn("transaction_type = 'WITHDRAWAL'", compiled.sql)


class TestDimensionFiltering(unittest.TestCase):
    def _sql_and_params(self, filt: QueryFilter):
        compiled = build_query(QueryRequest(metrics=("gross_sales",), filters=(filt,)))
        return compiled.sql, compiled.params

    def test_eq_operator(self) -> None:
        sql, params = self._sql_and_params(
            QueryFilter("product_category", FilterOperator.EQ, "Beverages")
        )
        self.assertRegex(sql, r"product_category = %\(p\d+\)s")
        self.assertIn("Beverages", params.values())
        self.assertNotIn("Beverages", sql)  # value must never be spliced into SQL text

    def test_ne_gt_gte_lt_lte(self) -> None:
        cases = {
            FilterOperator.NE: "!=",
            FilterOperator.GT: ">",
            FilterOperator.GTE: ">=",
            FilterOperator.LT: "<",
            FilterOperator.LTE: "<=",
        }
        for op, symbol in cases.items():
            with self.subTest(op=op):
                sql, _ = self._sql_and_params(QueryFilter("product_category", op, "X"))
                self.assertIn(f"product_category {symbol} %(", sql)

    def test_like_operator(self) -> None:
        sql, params = self._sql_and_params(
            QueryFilter("product_category", FilterOperator.LIKE, "%snack%")
        )
        self.assertIn("product_category LIKE %(", sql)
        self.assertIn("%snack%", params.values())

    def test_in_operator_uses_any_array_param(self) -> None:
        sql, params = self._sql_and_params(
            QueryFilter("product_category", FilterOperator.IN, ["A", "B", "C"])
        )
        self.assertRegex(sql, r"product_category = ANY\(%\(p\d+\)s\)")
        self.assertIn(["A", "B", "C"], params.values())

    def test_not_in_operator(self) -> None:
        sql, params = self._sql_and_params(
            QueryFilter("product_category", FilterOperator.NOT_IN, ["A", "B"])
        )
        self.assertRegex(sql, r"NOT \(product_category = ANY\(%\(p\d+\)s\)\)")

    def test_is_null_and_is_not_null(self) -> None:
        sql, params = self._sql_and_params(
            QueryFilter("product_category", FilterOperator.IS_NULL)
        )
        self.assertIn("product_category IS NULL", sql)
        self.assertEqual(params, {})  # nullary operators bind nothing

        sql, params = self._sql_and_params(
            QueryFilter("product_category", FilterOperator.IS_NOT_NULL)
        )
        self.assertIn("product_category IS NOT NULL", sql)

    def test_between_operator_binds_two_params(self) -> None:
        sql, params = self._sql_and_params(
            QueryFilter("product_category", FilterOperator.BETWEEN, ("A", "M"))
        )
        self.assertRegex(sql, r"product_category BETWEEN %\(p\d+\)s AND %\(p\d+\)s")
        self.assertEqual(sorted(params.values()), ["A", "M"])

    def test_multiple_filters_are_and_joined(self) -> None:
        compiled = build_query(
            QueryRequest(
                metrics=("gross_sales",),
                filters=(
                    QueryFilter("product_category", FilterOperator.EQ, "A"),
                    QueryFilter("customer_id", FilterOperator.EQ, "C1"),
                ),
            )
        )
        self.assertIn(" AND ", compiled.sql)
        self.assertEqual(len(compiled.params), 2)

    def test_filter_value_never_leaks_into_sql_text(self) -> None:
        malicious_value = "x'; DROP TABLE analytics.v_sales; --"
        compiled = build_query(
            QueryRequest(
                metrics=("gross_sales",),
                filters=(QueryFilter("product_category", FilterOperator.EQ, malicious_value),),
            )
        )
        self.assertNotIn(malicious_value, compiled.sql)
        self.assertIn(malicious_value, compiled.params.values())


class TestTimeFiltering(unittest.TestCase):
    def test_each_grain_produces_correct_date_trunc(self) -> None:
        expected_unit = {
            "daily": "day",
            "weekly": "week",
            "monthly": "month",
            "quarterly": "quarter",
            "yearly": "year",
        }
        for grain, unit in expected_unit.items():
            with self.subTest(grain=grain):
                compiled = build_query(QueryRequest(metrics=("gross_sales",), time_grain=grain))
                self.assertIn(f"date_trunc('{unit}', sale_date)", compiled.sql)

    def test_date_trunc_uses_view_specific_primary_date_column(self) -> None:
        # analytics.v_expenses uses expense_date, not sale_date.
        compiled = build_query(QueryRequest(metrics=("total_expenses",), time_grain="monthly"))
        self.assertIn("date_trunc('month', expense_date)", compiled.sql)

    def test_custom_date_range_binds_params_not_literals(self) -> None:
        compiled = build_query(
            QueryRequest(
                metrics=("gross_sales",),
                date_from=date(2026, 1, 1),
                date_to=date(2026, 3, 31),
            )
        )
        self.assertIn("sale_date >= %(", compiled.sql)
        self.assertIn("sale_date <= %(", compiled.sql)
        self.assertIn(date(2026, 1, 1), compiled.params.values())
        self.assertIn(date(2026, 3, 31), compiled.params.values())

    def test_unsupported_grain_raises_valueerror_at_time_grains_layer(self) -> None:
        # Every registered metric currently supports all 5 grains, so this
        # branch is unreachable through the public build_query() path today
        # (validate_query rejects unknown grains first). Exercise the
        # underlying function directly so it's still covered.
        with self.assertRaises(ValueError):
            date_trunc_expression("analytics.v_sales", "biannual")  # type: ignore[arg-type]


class TestGrouping(unittest.TestCase):
    def test_monthly_sales_groups_by_period_only(self) -> None:
        compiled = build_query(QueryRequest(metrics=("gross_sales",), time_grain="monthly"))
        self.assertIn("GROUP BY period", compiled.sql)

    def test_sales_by_customer_groups_by_dimension_only(self) -> None:
        compiled = build_query(
            QueryRequest(metrics=("gross_sales",), dimensions=("customer_name",))
        )
        self.assertIn("GROUP BY customer_name", compiled.sql)

    def test_monthly_sales_by_product_groups_by_both(self) -> None:
        compiled = build_query(
            QueryRequest(
                metrics=("gross_sales",),
                dimensions=("product_name",),
                time_grain="monthly",
            )
        )
        self.assertIn("GROUP BY product_name, period", compiled.sql)

    def test_no_group_by_when_no_dimensions_or_grain(self) -> None:
        compiled = build_query(QueryRequest(metrics=("gross_sales",)))
        self.assertNotIn("GROUP BY", compiled.sql)


class TestOrderByAndLimit(unittest.TestCase):
    def test_order_by_renders_direction(self) -> None:
        compiled = build_query(
            QueryRequest(
                metrics=("gross_sales",),
                dimensions=("product_category",),
                order_by=(OrderBy("gross_sales", "desc"), OrderBy("product_category", "asc")),
            )
        )
        self.assertIn("ORDER BY gross_sales DESC, product_category ASC", compiled.sql)

    def test_limit_is_parameterized(self) -> None:
        compiled = build_query(QueryRequest(metrics=("gross_sales",), limit=25))
        self.assertRegex(compiled.sql, r"LIMIT %\(p\d+\)s")
        self.assertIn(25, compiled.params.values())


class TestEdgeCases(unittest.TestCase):
    def test_invalid_metric_name_raises_validation_error_before_build(self) -> None:
        with self.assertRaises(ValidationError):
            build_query(QueryRequest(metrics=("totally_fake_metric",)))

    def test_unsupported_dimension_raises_validation_error_before_build(self) -> None:
        with self.assertRaises(ValidationError):
            build_query(QueryRequest(metrics=("gross_sales",), dimensions=("not_real",)))

    def test_invalid_date_range_raises_validation_error_before_build(self) -> None:
        with self.assertRaises(ValidationError):
            build_query(
                QueryRequest(
                    metrics=("gross_sales",),
                    date_from=date(2026, 6, 1),
                    date_to=date(2026, 1, 1),
                )
            )

    def test_ratio_metric_raises_build_error(self) -> None:
        # No ratio metrics are registered yet; simulate one to exercise the
        # rejection path documented in BuildError's docstring.
        fake_ratio = MetricDefinition(
            name="__test_ratio__",
            display_name="Test Ratio",
            description="synthetic metric for edge-case coverage",
            source_view="analytics.v_sales",
            aggregation="ratio",
            expression="SUM(a) / SUM(b)",
            filters=("some_condition = 1",),
            supported_dimensions=(),
            supported_time_grains=("monthly",),
            output_field="test_ratio",
        )
        METRIC_REGISTRY["__test_ratio__"] = fake_ratio
        try:
            with self.assertRaises(BuildError):
                build_query(QueryRequest(metrics=("__test_ratio__",)))
        finally:
            del METRIC_REGISTRY["__test_ratio__"]

    def test_ratio_metric_without_filters_is_a_known_latent_passthrough(self) -> None:
        # Documented KNOWN LIMITATION: a ratio metric with NO built-in
        # filters skips the CASE WHEN rewrap entirely and its expression is
        # spliced in as-is. This test pins down that documented behavior so
        # a future fix (Phase 8.3 numerator/denominator support) is a
        # deliberate, visible change to this test rather than a silent one.
        fake_ratio = MetricDefinition(
            name="__test_ratio_no_filters__",
            display_name="Test Ratio No Filters",
            description="synthetic metric for edge-case coverage",
            source_view="analytics.v_sales",
            aggregation="ratio",
            expression="SUM(a) / NULLIF(SUM(b), 0)",
            filters=(),
            supported_dimensions=(),
            supported_time_grains=("monthly",),
            output_field="test_ratio",
        )
        METRIC_REGISTRY["__test_ratio_no_filters__"] = fake_ratio
        try:
            compiled = build_query(QueryRequest(metrics=("__test_ratio_no_filters__",)))
            self.assertIn("SUM(a) / NULLIF(SUM(b), 0)", compiled.sql)
        finally:
            del METRIC_REGISTRY["__test_ratio_no_filters__"]

    def test_expression_aggregation_mismatch_raises_build_error_when_filters_present(
        self,
    ) -> None:
        # The mismatch check lives in _inner_expression(), which is only
        # invoked on the CASE-WHEN (metric.filters truthy) path — so this
        # metric needs built-in filters to actually exercise the check.
        broken_metric = MetricDefinition(
            name="__test_broken__",
            display_name="Broken",
            description="synthetic metric: aggregation/expression mismatch",
            source_view="analytics.v_sales",
            aggregation="sum",
            expression="COUNT(gross_sales)",  # doesn't match SUM(...) shape
            filters=("some_condition = 1",),
            supported_dimensions=(),
            supported_time_grains=("monthly",),
            output_field="broken",
        )
        METRIC_REGISTRY["__test_broken__"] = broken_metric
        try:
            with self.assertRaises(BuildError):
                build_query(QueryRequest(metrics=("__test_broken__",)))
        finally:
            del METRIC_REGISTRY["__test_broken__"]

    def test_expression_aggregation_mismatch_is_a_known_latent_passthrough_without_filters(
        self,
    ) -> None:
        # KNOWN LIMITATION (broader than the ratio-specific one documented
        # on BuildError): when a metric has NO built-in filters, its
        # `expression` is spliced in as-is regardless of whether it matches
        # `aggregation` at all -- _inner_expression() (and therefore the
        # mismatch check) is only reached via the CASE-WHEN path. This test
        # pins the current behavior down so a future fix is a deliberate,
        # visible change rather than a silent one.
        mismatched_metric = MetricDefinition(
            name="__test_mismatch_no_filters__",
            display_name="Mismatch No Filters",
            description="synthetic metric: aggregation/expression mismatch, no filters",
            source_view="analytics.v_sales",
            aggregation="sum",
            expression="COUNT(gross_sales)",  # declared 'sum' but not a SUM(...)
            filters=(),
            supported_dimensions=(),
            supported_time_grains=("monthly",),
            output_field="mismatch",
        )
        METRIC_REGISTRY["__test_mismatch_no_filters__"] = mismatched_metric
        try:
            compiled = build_query(QueryRequest(metrics=("__test_mismatch_no_filters__",)))
            self.assertIn("COALESCE(COUNT(gross_sales), 0) AS mismatch", compiled.sql)
        finally:
            del METRIC_REGISTRY["__test_mismatch_no_filters__"]

    def test_malicious_dimension_identifier_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            build_query(
                QueryRequest(
                    metrics=("gross_sales",),
                    dimensions=("product_category; DROP TABLE analytics.v_sales;",),
                )
            )

    def test_malicious_order_by_field_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            build_query(
                QueryRequest(
                    metrics=("gross_sales",),
                    order_by=(OrderBy("gross_sales; DROP TABLE analytics.v_sales;"),),
                )
            )


if __name__ == "__main__":
    unittest.main()
