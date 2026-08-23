"""Phase 9.4 -- time_resolver tests."""

from __future__ import annotations

import unittest
from datetime import date

from etl.analytics.schemas.analytical_query import AnalyticalQueryRequest
from etl.analytics.schemas.time_range import TimeRange
from etl.analytics.semantic.models import ResolutionStatus, SemanticResolutionError
from etl.analytics.semantic.time_resolver import (
    resolve_analytical_query_time,
    resolve_time_range,
)

# Anchor every test to a fixed Wednesday so weekday/month/quarter math
# doesn't depend on when the suite happens to run.
_TODAY = date(2026, 8, 19)  # Wednesday, August 19, 2026


class TestPassthroughCases(unittest.TestCase):
    def test_none_resolves_to_none(self) -> None:
        result = resolve_time_range(None, today=_TODAY)
        self.assertTrue(result.is_resolved)
        self.assertIsNone(result.resolved_value)

    def test_already_resolved_range_passes_through_unchanged(self) -> None:
        tr = TimeRange.for_dates(date(2026, 1, 1), date(2026, 3, 31))
        result = resolve_time_range(tr, today=_TODAY)
        self.assertTrue(result.is_resolved)
        self.assertIs(result.resolved_value, tr)


class TestSimpleDayPresets(unittest.TestCase):
    def test_today(self) -> None:
        result = resolve_time_range(TimeRange.for_preset("today"), today=_TODAY)
        self.assertEqual(result.resolved_value.start, date(2026, 8, 19))
        self.assertEqual(result.resolved_value.end, date(2026, 8, 19))

    def test_yesterday(self) -> None:
        result = resolve_time_range(TimeRange.for_preset("yesterday"), today=_TODAY)
        self.assertEqual(result.resolved_value.start, date(2026, 8, 18))
        self.assertEqual(result.resolved_value.end, date(2026, 8, 18))


class TestWeekPresets(unittest.TestCase):
    def test_current_week_is_monday_to_sunday(self) -> None:
        result = resolve_time_range(TimeRange.for_preset("current_week"), today=_TODAY)
        self.assertEqual(result.resolved_value.start, date(2026, 8, 17))  # Monday
        self.assertEqual(result.resolved_value.end, date(2026, 8, 23))  # Sunday

    def test_last_week(self) -> None:
        result = resolve_time_range(TimeRange.for_preset("last_week"), today=_TODAY)
        self.assertEqual(result.resolved_value.start, date(2026, 8, 10))
        self.assertEqual(result.resolved_value.end, date(2026, 8, 16))


class TestMonthPresets(unittest.TestCase):
    def test_current_month(self) -> None:
        result = resolve_time_range(TimeRange.for_preset("current_month"), today=_TODAY)
        self.assertEqual(result.resolved_value.start, date(2026, 8, 1))
        self.assertEqual(result.resolved_value.end, date(2026, 8, 31))

    def test_last_month(self) -> None:
        result = resolve_time_range(TimeRange.for_preset("last_month"), today=_TODAY)
        self.assertEqual(result.resolved_value.start, date(2026, 7, 1))
        self.assertEqual(result.resolved_value.end, date(2026, 7, 31))

    def test_last_month_handles_january_year_rollover(self) -> None:
        result = resolve_time_range(
            TimeRange.for_preset("last_month"), today=date(2026, 1, 15)
        )
        self.assertEqual(result.resolved_value.start, date(2025, 12, 1))
        self.assertEqual(result.resolved_value.end, date(2025, 12, 31))

    def test_month_to_date(self) -> None:
        result = resolve_time_range(TimeRange.for_preset("month_to_date"), today=_TODAY)
        self.assertEqual(result.resolved_value.start, date(2026, 8, 1))
        self.assertEqual(result.resolved_value.end, date(2026, 8, 19))


class TestQuarterPresets(unittest.TestCase):
    def test_current_quarter(self) -> None:
        # August is in Q3 (Jul-Sep).
        result = resolve_time_range(TimeRange.for_preset("current_quarter"), today=_TODAY)
        self.assertEqual(result.resolved_value.start, date(2026, 7, 1))
        self.assertEqual(result.resolved_value.end, date(2026, 9, 30))

    def test_last_quarter(self) -> None:
        result = resolve_time_range(TimeRange.for_preset("last_quarter"), today=_TODAY)
        self.assertEqual(result.resolved_value.start, date(2026, 4, 1))
        self.assertEqual(result.resolved_value.end, date(2026, 6, 30))

    def test_last_quarter_handles_year_rollover(self) -> None:
        # Q1 (Jan-Mar) -> last quarter is Q4 of the previous year.
        result = resolve_time_range(
            TimeRange.for_preset("last_quarter"), today=date(2026, 2, 10)
        )
        self.assertEqual(result.resolved_value.start, date(2025, 10, 1))
        self.assertEqual(result.resolved_value.end, date(2025, 12, 31))


class TestYearPresets(unittest.TestCase):
    def test_current_year(self) -> None:
        result = resolve_time_range(TimeRange.for_preset("current_year"), today=_TODAY)
        self.assertEqual(result.resolved_value.start, date(2026, 1, 1))
        self.assertEqual(result.resolved_value.end, date(2026, 12, 31))

    def test_last_year(self) -> None:
        result = resolve_time_range(TimeRange.for_preset("last_year"), today=_TODAY)
        self.assertEqual(result.resolved_value.start, date(2025, 1, 1))
        self.assertEqual(result.resolved_value.end, date(2025, 12, 31))

    def test_year_to_date(self) -> None:
        result = resolve_time_range(TimeRange.for_preset("year_to_date"), today=_TODAY)
        self.assertEqual(result.resolved_value.start, date(2026, 1, 1))
        self.assertEqual(result.resolved_value.end, date(2026, 8, 19))


class TestRollingWindowPresets(unittest.TestCase):
    def test_last_7_days_is_inclusive_of_today(self) -> None:
        result = resolve_time_range(TimeRange.for_preset("last_7_days"), today=_TODAY)
        self.assertEqual(result.resolved_value.start, date(2026, 8, 13))
        self.assertEqual(result.resolved_value.end, date(2026, 8, 19))
        self.assertEqual((result.resolved_value.end - result.resolved_value.start).days, 6)

    def test_last_30_days(self) -> None:
        result = resolve_time_range(TimeRange.for_preset("last_30_days"), today=_TODAY)
        self.assertEqual((result.resolved_value.end - result.resolved_value.start).days, 29)
        self.assertEqual(result.resolved_value.end, _TODAY)

    def test_last_90_days(self) -> None:
        result = resolve_time_range(TimeRange.for_preset("last_90_days"), today=_TODAY)
        self.assertEqual((result.resolved_value.end - result.resolved_value.start).days, 89)


class TestAllTime(unittest.TestCase):
    def test_all_time_resolves_with_no_bounds(self) -> None:
        result = resolve_time_range(TimeRange.for_preset("all_time"), today=_TODAY)
        self.assertTrue(result.is_resolved)
        self.assertIsNone(result.resolved_value.start)
        self.assertIsNone(result.resolved_value.end)
        # And the resolved TimeRange itself reports resolved too --
        # this is what lets it flow through
        # AnalyticalQueryRequest.is_ready_for_query_layer().
        self.assertTrue(result.resolved_value.is_resolved)


class TestLabelsAreNotResolved(unittest.TestCase):
    def test_label_is_not_found(self) -> None:
        result = resolve_time_range(TimeRange.for_label("Eid week"), today=_TODAY)
        self.assertEqual(result.status, ResolutionStatus.NOT_FOUND)
        self.assertIn("Eid week", result.message) # type: ignore


class TestResolveAnalyticalQueryTime(unittest.TestCase):
    def test_resolves_preset_in_place(self) -> None:
        request = AnalyticalQueryRequest(
            metric="gross_sales", time_range=TimeRange.for_preset("last_month")
        )
        resolved = resolve_analytical_query_time(request, today=_TODAY)
        self.assertIsNot(resolved, request)
        assert resolved.time_range is not None
        self.assertEqual(resolved.time_range.start, date(2026, 7, 1))
        self.assertEqual(resolved.time_range.end, date(2026, 7, 31))
        self.assertTrue(resolved.is_ready_for_query_layer())

    def test_no_time_range_is_a_no_op(self) -> None:
        request = AnalyticalQueryRequest(metric="gross_sales")
        resolved = resolve_analytical_query_time(request, today=_TODAY)
        self.assertIs(resolved, request)

    def test_already_resolved_time_range_is_a_no_op(self) -> None:
        request = AnalyticalQueryRequest(
            metric="gross_sales",
            time_range=TimeRange.for_dates(date(2026, 1, 1), date(2026, 1, 31)),
        )
        resolved = resolve_analytical_query_time(request, today=_TODAY)
        self.assertIs(resolved, request)

    def test_unresolvable_label_raises(self) -> None:
        request = AnalyticalQueryRequest(
            metric="gross_sales", time_range=TimeRange.for_label("Eid week")
        )
        with self.assertRaises(SemanticResolutionError) as ctx:
            resolve_analytical_query_time(request, today=_TODAY)
        self.assertEqual(len(ctx.exception.issues), 1)
        self.assertEqual(ctx.exception.issues[0].field_name, "time_range")

    def test_other_fields_are_carried_through_unchanged(self) -> None:
        request = AnalyticalQueryRequest(
            metric="gross_sales",
            dimensions=("customer_name",),
            raw_question="How much did we sell last month?",
            time_range=TimeRange.for_preset("last_month"),
        )
        resolved = resolve_analytical_query_time(request, today=_TODAY)
        self.assertEqual(resolved.metric, "gross_sales")
        self.assertEqual(resolved.dimensions, ("customer_name",))
        self.assertEqual(resolved.raw_question, "How much did we sell last month?")


class TestEndToEndThroughPhase8(unittest.TestCase):
    """The full pipeline the module docstring describes: a preset
    resolves to dates, and the resulting request is compilable."""

    def test_preset_flows_through_to_compiled_sql(self) -> None:
        from etl.analytics.query import build_query

        request = AnalyticalQueryRequest(
            metric="gross_sales", time_range=TimeRange.for_preset("current_month")
        )
        time_resolved = resolve_analytical_query_time(request, today=_TODAY)
        compiled = build_query(time_resolved.to_query_request())

        self.assertIn("FROM analytics.v_sales", compiled.sql)
        self.assertEqual(compiled.params["p1"], date(2026, 8, 1))
        self.assertEqual(compiled.params["p2"], date(2026, 8, 31))

    def test_all_time_flows_through_with_no_date_filter(self) -> None:
        from etl.analytics.query import build_query

        request = AnalyticalQueryRequest(
            metric="gross_sales", time_range=TimeRange.for_preset("all_time")
        )
        time_resolved = resolve_analytical_query_time(request, today=_TODAY)
        compiled = build_query(time_resolved.to_query_request())

        self.assertNotIn("WHERE", compiled.sql)


if __name__ == "__main__":
    unittest.main()
