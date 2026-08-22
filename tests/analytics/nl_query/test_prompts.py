"""Phase 9.2 -- prompt construction tests."""

from __future__ import annotations

import unittest
from datetime import date

from etl.analytics.schemas import KNOWN_PRESETS, KNOWN_TIME_GRAINS
from etl.analytics.nl_query.prompts import MetricHint, build_system_prompt


class TestBuildSystemPrompt(unittest.TestCase):
    def test_baseline_prompt_has_no_date_line_without_today(self) -> None:
        prompt = build_system_prompt()
        self.assertNotIn("Today's date is", prompt)

    def test_today_included_when_given(self) -> None:
        prompt = build_system_prompt(today=date(2026, 8, 22))
        self.assertIn("Today's date is 2026-08-22.", prompt)

    def test_mentions_every_known_time_grain(self) -> None:
        prompt = build_system_prompt()
        for grain in KNOWN_TIME_GRAINS:
            self.assertIn(grain, prompt)

    def test_mentions_every_known_preset(self) -> None:
        prompt = build_system_prompt()
        for preset in KNOWN_PRESETS:
            self.assertIn(preset, prompt)

    def test_instructs_json_only_response(self) -> None:
        prompt = build_system_prompt()
        self.assertIn("Return ONLY the JSON object", prompt)

    def test_no_metric_hints_section_when_none_given(self) -> None:
        prompt = build_system_prompt()
        self.assertNotIn("Metrics you can choose", prompt)

    def test_metric_hints_included(self) -> None:
        prompt = build_system_prompt(
            metric_hints=(MetricHint("gross_sales", "Total sales before returns"),)
        )
        self.assertIn("gross_sales", prompt)
        self.assertIn("Total sales before returns", prompt)

    def test_metric_hint_without_description(self) -> None:
        prompt = build_system_prompt(metric_hints=(MetricHint("gross_sales"),))
        self.assertIn("gross_sales", prompt)

    def test_dimension_hints_included(self) -> None:
        prompt = build_system_prompt(dimension_hints=("customer_name", "product_category"))
        self.assertIn("customer_name", prompt)
        self.assertIn("product_category", prompt)

    def test_mentions_not_writing_sql(self) -> None:
        prompt = build_system_prompt()
        self.assertIn("write sql", prompt.lower())


if __name__ == "__main__":
    unittest.main()
