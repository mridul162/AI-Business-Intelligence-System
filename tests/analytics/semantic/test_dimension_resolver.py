"""Phase 9.3.3 -- dimension_resolver tests."""

from __future__ import annotations

import unittest

from etl.analytics.semantic.dimension_resolver import resolve_dimension
from etl.analytics.semantic.models import ResolutionStatus

# gross_sales' supported_dimensions, used as a realistic allowed-set
# in most tests below.
_GROSS_SALES_DIMS = frozenset(
    {
        "customer_id",
        "customer_name",
        "product_id",
        "product_name",
        "product_category",
        "location_id",
        "location_name",
    }
)


class TestAlreadyCanonical(unittest.TestCase):
    def test_exact_supported_column_name(self) -> None:
        result = resolve_dimension("product_category", allowed_dimensions=_GROSS_SALES_DIMS)
        self.assertTrue(result.is_resolved)
        self.assertEqual(result.resolved_value, "product_category")

    def test_canonical_name_modulo_casing(self) -> None:
        result = resolve_dimension("Product Category", allowed_dimensions=_GROSS_SALES_DIMS)
        self.assertTrue(result.is_resolved)
        self.assertEqual(result.resolved_value, "product_category")


class TestAliasResolution(unittest.TestCase):
    def test_customer_alias(self) -> None:
        result = resolve_dimension("customer", allowed_dimensions=_GROSS_SALES_DIMS)
        self.assertTrue(result.is_resolved)
        self.assertEqual(result.resolved_value, "customer_name")

    def test_buyer_alias(self) -> None:
        result = resolve_dimension("buyer", allowed_dimensions=_GROSS_SALES_DIMS)
        self.assertEqual(result.resolved_value, "customer_name")

    def test_product_alias(self) -> None:
        result = resolve_dimension("item", allowed_dimensions=_GROSS_SALES_DIMS)
        self.assertEqual(result.resolved_value, "product_name")

    def test_location_alias(self) -> None:
        result = resolve_dimension("branch", allowed_dimensions=_GROSS_SALES_DIMS)
        self.assertEqual(result.resolved_value, "location_name")


class TestMetricDimensionCompatibility(unittest.TestCase):
    """A dimension that's canonical/known SOMEWHERE but not supported
    by the requested metric(s) is a compatibility failure, not a
    'never heard of it' failure."""

    def test_known_but_unsupported_column_is_invalid_not_not_found(self) -> None:
        # supplier_name is a real column (on v_purchases), but not
        # supported by gross_sales.
        result = resolve_dimension("supplier_name", allowed_dimensions=_GROSS_SALES_DIMS)
        self.assertEqual(result.status, ResolutionStatus.INVALID)

    def test_alias_to_unsupported_dimension_is_invalid(self) -> None:
        result = resolve_dimension("supplier", allowed_dimensions=_GROSS_SALES_DIMS)
        self.assertEqual(result.status, ResolutionStatus.INVALID)
        self.assertIn("supplier_name", result.message) # type: ignore


class TestNotFound(unittest.TestCase):
    def test_completely_unknown_term(self) -> None:
        result = resolve_dimension("weather", allowed_dimensions=_GROSS_SALES_DIMS)
        self.assertEqual(result.status, ResolutionStatus.NOT_FOUND)


class TestInvalidInput(unittest.TestCase):
    def test_empty_value(self) -> None:
        result = resolve_dimension("", allowed_dimensions=_GROSS_SALES_DIMS)
        self.assertEqual(result.status, ResolutionStatus.INVALID)


if __name__ == "__main__":
    unittest.main()
