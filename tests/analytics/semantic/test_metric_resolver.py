"""Phase 9.3.2 -- metric_resolver tests."""

from __future__ import annotations

import unittest

from etl.analytics.metrics.registry import METRIC_REGISTRY
from etl.analytics.semantic.metric_resolver import resolve_metric
from etl.analytics.semantic.models import ResolutionStatus


class TestExactAndDisplayNameMatch(unittest.TestCase):
    def test_exact_registry_name(self) -> None:
        result = resolve_metric("gross_sales")
        self.assertTrue(result.is_resolved)
        self.assertEqual(result.resolved_value, "gross_sales")

    def test_case_and_whitespace_insensitive_name_match(self) -> None:
        result = resolve_metric("  Gross_Sales  ")
        self.assertTrue(result.is_resolved)
        self.assertEqual(result.resolved_value, "gross_sales")

    def test_display_name_match(self) -> None:
        result = resolve_metric("Gross Sales")
        self.assertTrue(result.is_resolved)
        self.assertEqual(result.resolved_value, "gross_sales")


class TestAliasMatch(unittest.TestCase):
    def test_unambiguous_alias(self) -> None:
        result = resolve_metric("revenue")
        self.assertTrue(result.is_resolved)
        self.assertEqual(result.resolved_value, "gross_sales")

    def test_unambiguous_alias_net_sales(self) -> None:
        result = resolve_metric("net revenue")
        self.assertTrue(result.is_resolved)
        self.assertEqual(result.resolved_value, "net_sales")

    def test_unambiguous_alias_margin(self) -> None:
        result = resolve_metric("profit")
        self.assertTrue(result.is_resolved)
        self.assertEqual(result.resolved_value, "gross_business_margin")

    def test_unambiguous_alias_payments(self) -> None:
        result = resolve_metric("collections")
        self.assertEqual(result.resolved_value, "total_payments")


class TestAmbiguity(unittest.TestCase):
    """The roadmap's central worked example: 'how much did we earn'
    must not silently resolve to one metric."""

    def test_earn_is_ambiguous(self) -> None:
        result = resolve_metric("earn")
        self.assertEqual(result.status, ResolutionStatus.AMBIGUOUS)
        self.assertEqual(
            set(result.candidates), {"gross_sales", "net_sales", "gross_business_margin"}
        )

    def test_earnings_is_ambiguous(self) -> None:
        result = resolve_metric("earnings")
        self.assertEqual(result.status, ResolutionStatus.AMBIGUOUS)

    def test_income_is_ambiguous(self) -> None:
        result = resolve_metric("income")
        self.assertEqual(result.status, ResolutionStatus.AMBIGUOUS)

    def test_ambiguous_result_carries_helpful_message(self) -> None:
        result = resolve_metric("earn")
        self.assertIn("gross_sales", result.message) # type: ignore
        self.assertIn("net_sales", result.message) # type: ignore


class TestNotFoundAndInvalid(unittest.TestCase):
    def test_unknown_term(self) -> None:
        result = resolve_metric("banana yield")
        self.assertEqual(result.status, ResolutionStatus.NOT_FOUND)

    def test_empty_value(self) -> None:
        result = resolve_metric("")
        self.assertEqual(result.status, ResolutionStatus.INVALID)

    def test_whitespace_only_value(self) -> None:
        result = resolve_metric("   ")
        self.assertEqual(result.status, ResolutionStatus.INVALID)


class TestFieldNamePassthrough(unittest.TestCase):
    def test_default_field_name(self) -> None:
        result = resolve_metric("gross_sales")
        self.assertEqual(result.field_name, "metric")

    def test_custom_field_name(self) -> None:
        result = resolve_metric("gross_sales", field_name="additional_metrics[0]")
        self.assertEqual(result.field_name, "additional_metrics[0]")


class TestRegistryConsistency(unittest.TestCase):
    def test_every_registered_metric_resolves_to_itself(self) -> None:
        for name in METRIC_REGISTRY:
            with self.subTest(metric=name):
                result = resolve_metric(name)
                self.assertTrue(result.is_resolved)
                self.assertEqual(result.resolved_value, name)


if __name__ == "__main__":
    unittest.main()
