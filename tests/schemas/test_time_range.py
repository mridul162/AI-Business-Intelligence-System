"""Phase 9.1 — TimeRange schema tests."""

from __future__ import annotations

import unittest
from datetime import date

from etl.analytics.schemas.time_range import KNOWN_PRESETS, TimeRange


class TestConstruction(unittest.TestCase):
    def test_preset_only_is_unresolved(self) -> None:
        tr = TimeRange.for_preset("last_month")
        self.assertFalse(tr.is_resolved)
        self.assertEqual(tr.preset, "last_month")

    def test_label_only_is_unresolved(self) -> None:
        tr = TimeRange.for_label("Eid week")
        self.assertFalse(tr.is_resolved)
        self.assertEqual(tr.label, "Eid week")

    def test_dates_only_is_resolved(self) -> None:
        tr = TimeRange.for_dates(date(2026, 8, 1), date(2026, 8, 31))
        self.assertTrue(tr.is_resolved)

    def test_single_sided_dates_is_resolved(self) -> None:
        self.assertTrue(TimeRange.for_dates(date(2026, 8, 1)).is_resolved)
        self.assertTrue(TimeRange(end=date(2026, 8, 31)).is_resolved)

    def test_preset_plus_resolved_dates_is_resolved(self) -> None:
        # Once the time resolver fills in dates, the preset stays for
        # display purposes but the range counts as resolved.
        tr = TimeRange(preset="last_month", start=date(2026, 7, 1), end=date(2026, 7, 31))
        self.assertTrue(tr.is_resolved)
        self.assertEqual(tr.preset, "last_month")

    def test_every_known_preset_constructs(self) -> None:
        for preset in KNOWN_PRESETS:
            with self.subTest(preset=preset):
                TimeRange.for_preset(preset)


class TestValidation(unittest.TestCase):
    def test_empty_range_rejected(self) -> None:
        with self.assertRaises(ValueError):
            TimeRange()

    def test_preset_and_label_together_rejected(self) -> None:
        with self.assertRaises(ValueError):
            TimeRange(preset="last_month", label="Eid week")

    def test_unknown_preset_rejected(self) -> None:
        with self.assertRaises(ValueError):
            TimeRange.for_preset("next_leap_year")

    def test_start_after_end_rejected(self) -> None:
        with self.assertRaises(ValueError):
            TimeRange.for_dates(date(2026, 8, 31), date(2026, 8, 1))

    def test_start_equal_end_accepted(self) -> None:
        TimeRange.for_dates(date(2026, 8, 1), date(2026, 8, 1))


if __name__ == "__main__":
    unittest.main()
