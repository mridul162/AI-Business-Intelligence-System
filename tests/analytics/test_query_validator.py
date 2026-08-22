"""
Phase 8.4 — Query validator tests.

Covers the roadmap's "Edge cases" checklist:
  - Invalid metric name
  - Unsupported dimension
  - Unsupported time grain
  - Invalid date range
  - Filters incompatible with a metric
  - order_by / limit malformed input

This is the security boundary, so these tests lean toward proving
that *bad* input is rejected, not just that good input passes.
"""

from __future__ import annotations

import unittest
from datetime import date

from etl.analytics.query.models import FilterOperator, OrderBy, QueryFilter, QueryRequest
from etl.analytics.query.validator import ValidationError, validate_query


class TestMetricResolution(unittest.TestCase):
    def test_unknown_metric_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            validate_query(QueryRequest(metrics=("not_a_real_metric",)))

    def test_empty_metrics_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            validate_query(QueryRequest(metrics=()))

    def test_metrics_from_different_views_rejected(self) -> None:
        # gross_sales -> analytics.v_sales, total_payments -> analytics.v_payments
        with self.assertRaises(ValidationError):
            validate_query(QueryRequest(metrics=("gross_sales", "total_payments")))

    def test_metrics_from_same_view_accepted(self) -> None:
        # cash_in and cash_out both target analytics.v_cash_transactions
        validated = validate_query(QueryRequest(metrics=("cash_in", "cash_out")))
        self.assertEqual(validated.source_view, "analytics.v_cash_transactions")
        self.assertEqual(len(validated.metrics), 2)


class TestDimensionValidation(unittest.TestCase):
    def test_unsupported_dimension_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            validate_query(
                QueryRequest(metrics=("gross_sales",), dimensions=("not_a_dimension",))
            )

    def test_supported_dimension_accepted(self) -> None:
        validated = validate_query(
            QueryRequest(metrics=("gross_sales",), dimensions=("product_category",))
        )
        self.assertIn("product_category", validated.allowed_dimensions)

    def test_malformed_dimension_identifier_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            validate_query(
                QueryRequest(
                    metrics=("gross_sales",),
                    dimensions=("product_category; DROP TABLE analytics.v_sales;",),
                )
            )

    def test_dimension_not_shared_across_requested_metrics_still_allowed(self) -> None:
        # allowed_dimensions is the UNION of each metric's supported_dimensions,
        # so a dimension only one of two requested metrics supports is fine.
        validated = validate_query(
            QueryRequest(
                metrics=("cash_in", "cash_out"),
                dimensions=("transaction_type",),
            )
        )
        self.assertIn("transaction_type", validated.allowed_dimensions)


class TestTimeGrainValidation(unittest.TestCase):
    def test_none_grain_always_ok(self) -> None:
        validate_query(QueryRequest(metrics=("gross_sales",), time_grain=None))

    def test_supported_grain_accepted(self) -> None:
        validate_query(QueryRequest(metrics=("gross_sales",), time_grain="monthly"))

    def test_grain_not_in_common_intersection_rejected(self) -> None:
        # Every registered metric currently supports all five grains, so to
        # exercise this rejection path we simulate a caller passing a grain
        # that isn't one of the (only) five known values at all.
        with self.assertRaises(ValidationError):
            validate_query(QueryRequest(metrics=("gross_sales",), time_grain="biannual"))  # type: ignore[arg-type]


class TestFilterValidation(unittest.TestCase):
    def test_filter_on_unsupported_dimension_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            validate_query(
                QueryRequest(
                    metrics=("gross_sales",),
                    filters=(QueryFilter("not_a_dimension", FilterOperator.EQ, "x"),),
                )
            )

    def test_filter_bad_identifier_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            validate_query(
                QueryRequest(
                    metrics=("gross_sales",),
                    filters=(
                        QueryFilter("product_category)) OR 1=1 --", FilterOperator.EQ, "x"),
                    ),
                )
            )

    def test_nullary_operator_with_value_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            validate_query(
                QueryRequest(
                    metrics=("gross_sales",),
                    filters=(
                        QueryFilter("product_category", FilterOperator.IS_NULL, "x"),
                    ),
                )
            )

    def test_nullary_operator_without_value_accepted(self) -> None:
        validate_query(
            QueryRequest(
                metrics=("gross_sales",),
                filters=(QueryFilter("product_category", FilterOperator.IS_NULL),),
            )
        )

    def test_list_operator_requires_nonempty_list(self) -> None:
        with self.assertRaises(ValidationError):
            validate_query(
                QueryRequest(
                    metrics=("gross_sales",),
                    filters=(QueryFilter("product_category", FilterOperator.IN, ()),),
                )
            )
        with self.assertRaises(ValidationError):
            validate_query(
                QueryRequest(
                    metrics=("gross_sales",),
                    filters=(QueryFilter("product_category", FilterOperator.IN, "not-a-list"),),
                )
            )

    def test_list_operator_with_values_accepted(self) -> None:
        validate_query(
            QueryRequest(
                metrics=("gross_sales",),
                filters=(
                    QueryFilter("product_category", FilterOperator.IN, ["A", "B"]),
                ),
            )
        )

    def test_between_requires_two_item_value(self) -> None:
        with self.assertRaises(ValidationError):
            validate_query(
                QueryRequest(
                    metrics=("gross_sales",),
                    filters=(
                        QueryFilter("product_category", FilterOperator.BETWEEN, ("A",)),
                    ),
                )
            )

    def test_scalar_operator_requires_value(self) -> None:
        with self.assertRaises(ValidationError):
            validate_query(
                QueryRequest(
                    metrics=("gross_sales",),
                    filters=(QueryFilter("product_category", FilterOperator.EQ, None),),
                )
            )


class TestDateRangeValidation(unittest.TestCase):
    def test_date_from_after_date_to_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            validate_query(
                QueryRequest(
                    metrics=("gross_sales",),
                    date_from=date(2026, 12, 31),
                    date_to=date(2026, 1, 1),
                )
            )

    def test_equal_dates_accepted(self) -> None:
        validate_query(
            QueryRequest(
                metrics=("gross_sales",),
                date_from=date(2026, 6, 1),
                date_to=date(2026, 6, 1),
            )
        )

    def test_one_sided_range_accepted(self) -> None:
        validate_query(QueryRequest(metrics=("gross_sales",), date_from=date(2026, 1, 1)))
        validate_query(QueryRequest(metrics=("gross_sales",), date_to=date(2026, 1, 1)))


class TestOrderByValidation(unittest.TestCase):
    def test_order_by_dimension_accepted(self) -> None:
        validate_query(
            QueryRequest(
                metrics=("gross_sales",),
                dimensions=("product_category",),
                order_by=(OrderBy("product_category"),),
            )
        )

    def test_order_by_output_field_accepted(self) -> None:
        validate_query(
            QueryRequest(metrics=("gross_sales",), order_by=(OrderBy("gross_sales", "desc"),))
        )

    def test_order_by_period_requires_time_grain(self) -> None:
        with self.assertRaises(ValidationError):
            validate_query(
                QueryRequest(metrics=("gross_sales",), order_by=(OrderBy("period"),))
            )
        validate_query(
            QueryRequest(
                metrics=("gross_sales",), time_grain="monthly", order_by=(OrderBy("period"),)
            )
        )

    def test_order_by_unknown_field_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            validate_query(
                QueryRequest(metrics=("gross_sales",), order_by=(OrderBy("nonsense_field"),))
            )

    def test_order_by_bad_direction_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            validate_query(
                QueryRequest(
                    metrics=("gross_sales",), order_by=(OrderBy("gross_sales", "sideways"),)
                )
            )


class TestLimitValidation(unittest.TestCase):
    def test_positive_limit_accepted(self) -> None:
        validate_query(QueryRequest(metrics=("gross_sales",), limit=10))

    def test_none_limit_accepted(self) -> None:
        validate_query(QueryRequest(metrics=("gross_sales",), limit=None))

    def test_zero_limit_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            validate_query(QueryRequest(metrics=("gross_sales",), limit=0))

    def test_negative_limit_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            validate_query(QueryRequest(metrics=("gross_sales",), limit=-5))

    def test_non_int_limit_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            validate_query(QueryRequest(metrics=("gross_sales",), limit=3.5))  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
