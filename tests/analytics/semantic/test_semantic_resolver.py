"""
Phase 9.3.5 -- SemanticResolver orchestrator tests.

Includes the roadmap's own worked examples reproduced end to end:
  - "How much did we earn last month?" -> ambiguous metric
  - "Show sales for Mirpur." -> location resolved to a canonical ID
  - "Show revenue by customer for Rahim this month" -> full pipeline
"""

from __future__ import annotations

import unittest

from etl.analytics.schemas import AnalyticalQueryRequest, FilterCondition, TimeRange
from etl.analytics.semantic import (
    EntityMatch,
    ResolutionStatus,
    SemanticResolutionError,
    SemanticResolver,
    StaticEntityDirectory,
)

_LOCATIONS = StaticEntityDirectory(
    {
        "location_name": [
            EntityMatch(id="LOC_001", name="Mirpur Branch"),
            EntityMatch(id="LOC_002", name="Gulshan Branch"),
        ]
    }
)

_CUSTOMERS = StaticEntityDirectory(
    {
        "customer_name": [
            EntityMatch(id="CUST_0042", name="Rahim"),
            EntityMatch(id="CUST_0099", name="Rahim Uddin"),
        ]
    }
)


class TestRoadmapExamples(unittest.TestCase):
    def test_ambiguous_earnings_metric(self) -> None:
        resolver = SemanticResolver()
        request = AnalyticalQueryRequest(
            metric="earn", time_range=TimeRange.for_preset("last_month")
        )
        with self.assertRaises(SemanticResolutionError) as ctx:
            resolver.resolve(request)
        issue = ctx.exception.issues[0]
        self.assertEqual(issue.status, ResolutionStatus.AMBIGUOUS)
        self.assertEqual(
            set(issue.candidates), {"gross_sales", "net_sales", "gross_business_margin"}
        )

    def test_location_filter_resolves_to_canonical_id(self) -> None:
        resolver = SemanticResolver(entity_lookup=_LOCATIONS)
        request = AnalyticalQueryRequest(
            metric="sales",
            filters=(FilterCondition("location", "eq", "Mirpur"),),
            raw_question="Show sales for Mirpur.",
        )
        resolved = resolver.resolve(request)
        self.assertEqual(resolved.metric, "gross_sales")
        self.assertEqual(len(resolved.filters), 1)
        self.assertEqual(resolved.filters[0].dimension, "location_id")
        self.assertEqual(resolved.filters[0].value, "LOC_001")

    def test_full_pipeline_example(self) -> None:
        resolver = SemanticResolver(entity_lookup=_CUSTOMERS)
        request = AnalyticalQueryRequest(
            metric="revenue",
            dimensions=("customer",),
            filters=(FilterCondition("customer", "eq", "Rahim"),),
            time_range=TimeRange.for_preset("current_month"),
            raw_question="Show revenue by customer for Rahim this month",
        )
        resolved = resolver.resolve(request)

        self.assertEqual(resolved.metric, "gross_sales")
        self.assertEqual(resolved.dimensions, ("customer_name",))
        self.assertEqual(resolved.filters[0].dimension, "customer_id")
        self.assertEqual(resolved.filters[0].value, "CUST_0042")
        # time_range untouched -- still Phase 9.4's job.
        assert resolved.time_range is not None
        self.assertEqual(resolved.time_range.preset, "current_month")
        self.assertFalse(resolved.time_range.is_resolved)
        self.assertEqual(resolved.raw_question, "Show revenue by customer for Rahim this month")


class TestMetricThenDimensionThenFilterOrdering(unittest.TestCase):
    def test_metric_failure_short_circuits_before_dimension_checks_run(self) -> None:
        # dimensions=("not_a_real_dimension",) would ALSO fail, but the
        # error should be about the metric, since dimension validity
        # can't even be evaluated without a resolved metric.
        resolver = SemanticResolver()
        request = AnalyticalQueryRequest(
            metric="not_a_real_metric", dimensions=("not_a_real_dimension",)
        )
        with self.assertRaises(SemanticResolutionError) as ctx:
            resolver.resolve(request)
        self.assertEqual(len(ctx.exception.issues), 1)
        self.assertEqual(ctx.exception.issues[0].field_name, "metric")

    def test_multiple_additional_metric_failures_all_reported(self) -> None:
        resolver = SemanticResolver()
        request = AnalyticalQueryRequest(
            metric="gross_sales", additional_metrics=("nope_one", "nope_two")
        )
        with self.assertRaises(SemanticResolutionError) as ctx:
            resolver.resolve(request)
        self.assertEqual(len(ctx.exception.issues), 2)


class TestBatchIssueCollection(unittest.TestCase):
    """Once the metric resolves, dimension AND filter issues should
    all be collected together in one error, not one-at-a-time."""

    def test_multiple_unrelated_issues_reported_together(self) -> None:
        resolver = SemanticResolver(entity_lookup=_LOCATIONS)
        request = AnalyticalQueryRequest(
            metric="gross_sales",
            dimensions=("not_a_real_dimension",),
            filters=(FilterCondition("location", "eq", "Nonexistent Place"),),
        )
        with self.assertRaises(SemanticResolutionError) as ctx:
            resolver.resolve(request)
        self.assertEqual(len(ctx.exception.issues), 2)
        field_names = {issue.field_name for issue in ctx.exception.issues}
        self.assertEqual(field_names, {"dimensions[0]", "filter:location"})


class TestMultiMetricRequest(unittest.TestCase):
    def test_additional_metrics_resolved_and_widen_allowed_dimensions(self) -> None:
        resolver = SemanticResolver()
        request = AnalyticalQueryRequest(
            metric="cash inflow",
            additional_metrics=("cash outflow",),
            dimensions=("transaction_type",),
        )
        resolved = resolver.resolve(request)
        self.assertEqual(resolved.metric, "cash_in")
        self.assertEqual(resolved.additional_metrics, ("cash_out",))
        self.assertEqual(resolved.dimensions, ("transaction_type",))


class TestNoOpWhenAlreadyCanonical(unittest.TestCase):
    def test_already_canonical_request_resolves_unchanged(self) -> None:
        resolver = SemanticResolver()
        request = AnalyticalQueryRequest(
            metric="gross_sales",
            dimensions=("product_category",),
            filters=(FilterCondition("product_category", "eq", "Snacks"),),
        )
        resolved = resolver.resolve(request)
        self.assertEqual(resolved.metric, "gross_sales")
        self.assertEqual(resolved.dimensions, ("product_category",))
        self.assertEqual(resolved.filters[0].dimension, "product_category")
        self.assertEqual(resolved.filters[0].value, "Snacks")


class TestBridgeBackToAnalyticalQueryRequest(unittest.TestCase):
    def test_to_analytical_query_request_round_trips(self) -> None:
        resolver = SemanticResolver(entity_lookup=_LOCATIONS)
        request = AnalyticalQueryRequest(
            metric="revenue",
            dimensions=("location",),
            filters=(FilterCondition("location", "eq", "Mirpur Branch"),),
        )
        resolved = resolver.resolve(request)
        bridged = resolved.to_analytical_query_request()

        self.assertEqual(bridged.metric, "gross_sales")
        self.assertEqual(bridged.dimensions, ("location_name",))
        self.assertEqual(bridged.filters[0].dimension, "location_id")
        self.assertEqual(bridged.filters[0].value, "LOC_001")

    def test_bridged_request_reaches_phase8_when_time_resolved(self) -> None:
        from datetime import date

        from etl.analytics.query import build_query

        resolver = SemanticResolver()
        request = AnalyticalQueryRequest(
            metric="revenue",
            dimensions=("product_category",),
            time_range=TimeRange.for_dates(date(2026, 1, 1), date(2026, 12, 31)),
        )
        resolved = resolver.resolve(request)
        bridged = resolved.to_analytical_query_request()
        self.assertTrue(bridged.is_ready_for_query_layer())
        compiled = build_query(bridged.to_query_request())
        self.assertIn("product_category", compiled.sql)
        self.assertIn("FROM analytics.v_sales", compiled.sql)


class TestSemanticResolverDoesNotGenerateSql(unittest.TestCase):
    """Design rule from the roadmap: this layer must not touch SQL."""

    def test_resolved_query_has_no_sql_producing_surface(self) -> None:
        resolver = SemanticResolver()
        request = AnalyticalQueryRequest(metric="gross_sales")
        resolved = resolver.resolve(request)
        self.assertFalse(hasattr(resolved, "sql"))
        self.assertFalse(hasattr(resolved, "to_query_request"))


if __name__ == "__main__":
    unittest.main()
