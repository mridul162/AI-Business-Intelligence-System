"""
Phase 9.1 — AnalyticalQueryRequest contract tests.

Covers:
  - structural validation (bad operator, bad limit, bad time_grain, etc.)
  - readiness checks (is_ready_for_query_layer)
  - the bridge into the existing Phase 8 query layer
    (to_query_request + build_query), including that an already-built
    QueryRequest still goes through Phase 8's own ValidationError for
    things this contract doesn't check itself (unknown metric names,
    unsupported dimensions).
"""

from __future__ import annotations

import unittest
from datetime import date

from etl.analytics.schemas.analytical_query import (
    AnalyticalQueryRequest,
    ComparisonSpec,
    FilterCondition,
    NotResolvedError,
    TimeRange,
)
from etl.analytics.query import ValidationError, build_query


class TestFilterConditionValidation(unittest.TestCase):
    def test_valid_operator_accepted(self) -> None:
        FilterCondition("product_category", "eq", "Beverages")

    def test_unknown_operator_rejected(self) -> None:
        with self.assertRaises(ValueError):
            FilterCondition("product_category", "smells_like", "Beverages")

    def test_empty_dimension_rejected(self) -> None:
        with self.assertRaises(ValueError):
            FilterCondition("", "eq", "x")

    def test_to_query_filter_round_trips_operator(self) -> None:
        qf = FilterCondition("product_category", "in", ["A", "B"]).to_query_filter()
        self.assertEqual(qf.dimension, "product_category")
        self.assertEqual(qf.operator.value, "in")
        self.assertEqual(qf.value, ["A", "B"])


class TestComparisonSpecValidation(unittest.TestCase):
    def test_known_mode_accepted(self) -> None:
        ComparisonSpec("previous_period")

    def test_unknown_mode_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ComparisonSpec("vibes_based")


class TestAnalyticalQueryRequestValidation(unittest.TestCase):
    def test_minimal_valid_request(self) -> None:
        AnalyticalQueryRequest(metric="gross_sales")

    def test_empty_metric_rejected(self) -> None:
        with self.assertRaises(ValueError):
            AnalyticalQueryRequest(metric="")

    def test_bad_sort_order_rejected(self) -> None:
        with self.assertRaises(ValueError):
            AnalyticalQueryRequest(metric="gross_sales", sort_order="sideways")

    def test_bad_time_grain_rejected(self) -> None:
        with self.assertRaises(ValueError):
            AnalyticalQueryRequest(metric="gross_sales", time_grain="biannual")

    def test_zero_and_negative_limit_rejected(self) -> None:
        with self.assertRaises(ValueError):
            AnalyticalQueryRequest(metric="gross_sales", limit=0)
        with self.assertRaises(ValueError):
            AnalyticalQueryRequest(metric="gross_sales", limit=-3)

    def test_bool_limit_rejected(self) -> None:
        # bool is a subclass of int in Python; make sure True/False
        # can't sneak through as limit=1/limit=0.
        with self.assertRaises(ValueError):
            AnalyticalQueryRequest(metric="gross_sales", limit=True)

    def test_non_int_limit_rejected(self) -> None:
        with self.assertRaises(ValueError):
            AnalyticalQueryRequest(metric="gross_sales", limit=3.5)  # type: ignore[arg-type]

    def test_all_metrics_property(self) -> None:
        req = AnalyticalQueryRequest(metric="cash_in", additional_metrics=("cash_out",))
        self.assertEqual(req.all_metrics, ("cash_in", "cash_out"))

    def test_all_metrics_property_single(self) -> None:
        req = AnalyticalQueryRequest(metric="gross_sales")
        self.assertEqual(req.all_metrics, ("gross_sales",))


class TestReadiness(unittest.TestCase):
    def test_ready_with_no_time_range(self) -> None:
        req = AnalyticalQueryRequest(metric="gross_sales")
        self.assertTrue(req.is_ready_for_query_layer())

    def test_ready_with_resolved_time_range(self) -> None:
        req = AnalyticalQueryRequest(
            metric="gross_sales",
            time_range=TimeRange.for_dates(date(2026, 8, 1), date(2026, 8, 31)),
        )
        self.assertTrue(req.is_ready_for_query_layer())

    def test_not_ready_with_unresolved_time_range(self) -> None:
        req = AnalyticalQueryRequest(
            metric="gross_sales", time_range=TimeRange.for_preset("last_month")
        )
        self.assertFalse(req.is_ready_for_query_layer())

    def test_not_ready_with_comparison(self) -> None:
        req = AnalyticalQueryRequest(
            metric="gross_sales", comparison=ComparisonSpec("previous_period")
        )
        self.assertFalse(req.is_ready_for_query_layer())


class TestToQueryRequest(unittest.TestCase):
    def test_unresolved_time_range_raises_not_resolved_error(self) -> None:
        req = AnalyticalQueryRequest(
            metric="gross_sales", time_range=TimeRange.for_preset("last_month")
        )
        with self.assertRaises(NotResolvedError):
            req.to_query_request()

    def test_comparison_raises_not_resolved_error(self) -> None:
        req = AnalyticalQueryRequest(
            metric="gross_sales", comparison=ComparisonSpec("previous_period")
        )
        with self.assertRaises(NotResolvedError):
            req.to_query_request()

    def test_resolved_request_converts_cleanly(self) -> None:
        req = AnalyticalQueryRequest(
            metric="gross_sales",
            dimensions=("product_category",),
            time_grain="monthly",
            time_range=TimeRange.for_dates(date(2026, 1, 1), date(2026, 12, 31)),
            filters=(FilterCondition("product_category", "eq", "Beverages"),),
            sort_by="gross_sales",
            sort_order="desc",
            limit=10,
        )
        qr = req.to_query_request()
        self.assertEqual(qr.metrics, ("gross_sales",))
        self.assertEqual(qr.dimensions, ("product_category",))
        self.assertEqual(qr.time_grain, "monthly")
        self.assertEqual(qr.date_from, date(2026, 1, 1))
        self.assertEqual(qr.date_to, date(2026, 12, 31))
        self.assertEqual(len(qr.filters), 1)
        self.assertEqual(qr.order_by[0].field, "gross_sales")
        self.assertEqual(qr.order_by[0].direction, "desc")
        self.assertEqual(qr.limit, 10)

    def test_multi_metric_request_converts(self) -> None:
        req = AnalyticalQueryRequest(metric="cash_in", additional_metrics=("cash_out",))
        qr = req.to_query_request()
        self.assertEqual(qr.metrics, ("cash_in", "cash_out"))

    def test_no_sort_by_means_no_order_by(self) -> None:
        req = AnalyticalQueryRequest(metric="gross_sales")
        qr = req.to_query_request()
        self.assertEqual(qr.order_by, ())

    def test_converted_request_compiles_through_existing_query_layer(self) -> None:
        req = AnalyticalQueryRequest(
            metric="gross_sales",
            dimensions=("product_category",),
            time_grain="monthly",
        )
        compiled = build_query(req.to_query_request())
        self.assertIn("product_category", compiled.sql)
        self.assertIn("date_trunc('month'", compiled.sql)

    def test_contract_does_not_pre_validate_metric_existence(self) -> None:
        # AnalyticalQueryRequest accepts any non-empty string as `metric`
        # (that's Phase 9.3's job to resolve/reject). The error should
        # only surface once it reaches Phase 8's build_query().
        req = AnalyticalQueryRequest(metric="not_a_real_metric_alias")
        qr = req.to_query_request()  # succeeds structurally
        with self.assertRaises(ValidationError):
            build_query(qr)  # fails at the actual safety boundary

    def test_contract_does_not_pre_validate_dimension_support(self) -> None:
        req = AnalyticalQueryRequest(metric="gross_sales", dimensions=("not_a_dimension",))
        qr = req.to_query_request()
        with self.assertRaises(ValidationError):
            build_query(qr)


class TestRawQuestionPassthrough(unittest.TestCase):
    def test_raw_question_is_carried_but_not_used_in_query_request(self) -> None:
        req = AnalyticalQueryRequest(
            metric="gross_sales", raw_question="What were sales in August?"
        )
        self.assertEqual(req.raw_question, "What were sales in August?")
        qr = req.to_query_request()
        self.assertNotIn("raw_question", qr.__dataclass_fields__)


if __name__ == "__main__":
    unittest.main()
