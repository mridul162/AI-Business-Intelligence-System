"""Phase 9.3.4 -- filter_resolver tests."""

from __future__ import annotations

import unittest

from etl.analytics.schemas import FilterCondition
from etl.analytics.semantic.filter_resolver import EntityMatch, StaticEntityDirectory, resolve_filter
from etl.analytics.semantic.models import ResolutionStatus

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


class TestDimensionResolutionFailsFirst(unittest.TestCase):
    def test_bad_dimension_short_circuits(self) -> None:
        result, resolved = resolve_filter(
            FilterCondition("not_a_dimension", "eq", "x"), allowed_dimensions=_GROSS_SALES_DIMS
        )
        self.assertFalse(result.is_resolved)
        self.assertIsNone(resolved)


class TestNullaryOperators(unittest.TestCase):
    def test_is_null_needs_no_value_resolution(self) -> None:
        result, resolved = resolve_filter(
            FilterCondition("customer", "is_null"), allowed_dimensions=_GROSS_SALES_DIMS
        )
        
        self.assertTrue(result.is_resolved)
        assert resolved is not None
        self.assertEqual(resolved.dimension, "customer_name")
        self.assertIsNone(resolved.value)


class TestEntityResolutionWithDirectory(unittest.TestCase):
    def test_exact_name_resolves_to_id_and_switches_dimension(self) -> None:
        result, resolved = resolve_filter(
            FilterCondition("location", "eq", "Mirpur Branch"),
            allowed_dimensions=_GROSS_SALES_DIMS,
            entity_lookup=_LOCATIONS,
        )
        self.assertTrue(result.is_resolved)
        assert resolved is not None
        self.assertEqual(resolved.dimension, "location_id")
        self.assertEqual(resolved.value, "LOC_001")
        self.assertEqual(resolved.original_dimension, "location")
        self.assertEqual(resolved.original_value, "Mirpur Branch")

    def test_partial_name_resolves_via_directory_substring_match(self) -> None:
        # "Mirpur" is a substring of "Mirpur Branch"; StaticEntityDirectory
        # returns it as the sole match -> unambiguous.
        result, resolved = resolve_filter(
            FilterCondition("location", "eq", "Mirpur"),
            allowed_dimensions=_GROSS_SALES_DIMS,
            entity_lookup=_LOCATIONS,
        )
        self.assertTrue(result.is_resolved)
        assert resolved is not None
        self.assertEqual(resolved.value, "LOC_001")

    def test_exact_match_wins_over_looser_matches(self) -> None:
        # "Rahim" is both an exact match AND a substring of "Rahim Uddin" --
        # the exact match must win, not be reported as ambiguous.
        result, resolved = resolve_filter(
            FilterCondition("customer", "eq", "Rahim"),
            allowed_dimensions=_GROSS_SALES_DIMS,
            entity_lookup=_CUSTOMERS,
        )
        self.assertTrue(result.is_resolved)
        assert resolved is not None
        self.assertEqual(resolved.value, "CUST_0042")

    def test_no_match_is_not_found(self) -> None:
        result, resolved = resolve_filter(
            FilterCondition("location", "eq", "Nonexistent Place"),
            allowed_dimensions=_GROSS_SALES_DIMS,
            entity_lookup=_LOCATIONS,
        )
        self.assertEqual(result.status, ResolutionStatus.NOT_FOUND)
        self.assertIsNone(resolved)

    def test_ambiguous_match_reports_candidates(self) -> None:
        # "Branch" substring-matches both locations.
        result, resolved = resolve_filter(
            FilterCondition("location", "eq", "Branch"),
            allowed_dimensions=_GROSS_SALES_DIMS,
            entity_lookup=_LOCATIONS,
        )
        self.assertEqual(result.status, ResolutionStatus.AMBIGUOUS)
        self.assertEqual(
            set(result.candidates), {"Mirpur Branch", "Gulshan Branch"}
        )
        self.assertIsNone(resolved)

    def test_in_operator_resolves_every_item(self) -> None:
        result, resolved = resolve_filter(
            FilterCondition("location", "in", ["Mirpur Branch", "Gulshan Branch"]),
            allowed_dimensions=_GROSS_SALES_DIMS,
            entity_lookup=_LOCATIONS,
        )
        self.assertTrue(result.is_resolved)
        assert resolved is not None
        self.assertEqual(resolved.dimension, "location_id")
        self.assertEqual(set(resolved.value), {"LOC_001", "LOC_002"})

    def test_in_operator_fails_if_any_item_unresolvable(self) -> None:
        result, resolved = resolve_filter(
            FilterCondition("location", "in", ["Mirpur Branch", "Nowhere"]),
            allowed_dimensions=_GROSS_SALES_DIMS,
            entity_lookup=_LOCATIONS,
        )
        self.assertFalse(result.is_resolved)
        self.assertIsNone(resolved)

    def test_in_operator_requires_nonempty_list(self) -> None:
        result, resolved = resolve_filter(
            FilterCondition("location", "in", []),
            allowed_dimensions=_GROSS_SALES_DIMS,
            entity_lookup=_LOCATIONS,
        )
        self.assertEqual(result.status, ResolutionStatus.INVALID)


class TestEntityResolutionWithoutDirectory(unittest.TestCase):
    def test_entity_dimension_passes_through_as_name_when_no_lookup_wired(self) -> None:
        result, resolved = resolve_filter(
            FilterCondition("location", "eq", "  Mirpur Branch  "),
            allowed_dimensions=_GROSS_SALES_DIMS,
            entity_lookup=None,
        )
        self.assertTrue(result.is_resolved)
        assert resolved is not None
        self.assertEqual(resolved.dimension, "location_name")  # NOT switched to *_id
        self.assertEqual(resolved.value, "Mirpur Branch")  # trimmed, not looked up


class TestNonEntityDimensionsPassThroughNormalized(unittest.TestCase):
    def test_categorical_dimension_value_is_trimmed_not_looked_up(self) -> None:
        result, resolved = resolve_filter(
            FilterCondition("product_category", "eq", "  Snacks  "),
            allowed_dimensions=_GROSS_SALES_DIMS,
            entity_lookup=_LOCATIONS,  # present, but product_category isn't an entity dim
        )
        self.assertTrue(result.is_resolved)
        assert resolved is not None
        self.assertEqual(resolved.dimension, "product_category")
        self.assertEqual(resolved.value, "Snacks")

    def test_like_operator_on_entity_dimension_is_not_id_resolved(self) -> None:
        # LIKE is a pattern search against the name column itself,
        # not something that should collapse to a single ID.
        result, resolved = resolve_filter(
            FilterCondition("location", "like", "%Mirpur%"),
            allowed_dimensions=_GROSS_SALES_DIMS,
            entity_lookup=_LOCATIONS,
        )
        self.assertTrue(result.is_resolved)
        assert resolved is not None
        self.assertEqual(resolved.dimension, "location_name")
        self.assertEqual(resolved.value, "%Mirpur%")

    def test_between_operator_on_entity_dimension_passes_through(self) -> None:
        result, resolved = resolve_filter(
            FilterCondition("location", "between", ("A", "M")),
            allowed_dimensions=_GROSS_SALES_DIMS,
            entity_lookup=_LOCATIONS,
        )
        self.assertTrue(result.is_resolved)
        assert resolved is not None
        self.assertEqual(resolved.dimension, "location_name")
        self.assertEqual(resolved.value, ["A", "M"])


if __name__ == "__main__":
    unittest.main()
