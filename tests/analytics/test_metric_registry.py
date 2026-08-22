"""
Phase 8.4 — Metric registry tests.

Covers the roadmap's "Each registered metric" checklist:
  - Can the metric be queried successfully (in isolation)?
  - Does the SQL return the expected output field?

These tests don't hit a database — they compile each metric to SQL
and inspect the CompiledQuery, which is as far as this layer goes
without a live connection.
"""

from __future__ import annotations

import unittest

from etl.analytics.metrics import METRIC_REGISTRY, get_metric, list_metrics
from etl.analytics.query import QueryRequest, build_query


class TestRegistryBasics(unittest.TestCase):
    def test_get_metric_returns_known_metric(self) -> None:
        metric = get_metric("gross_sales")
        self.assertEqual(metric.name, "gross_sales")

    def test_get_metric_unknown_name_raises_keyerror(self) -> None:
        with self.assertRaises(KeyError):
            get_metric("does_not_exist")

    def test_list_metrics_matches_registry_size(self) -> None:
        self.assertEqual(len(list_metrics()), len(METRIC_REGISTRY))

    def test_list_metrics_returns_metric_definitions(self) -> None:
        for metric in list_metrics():
            self.assertEqual(metric, METRIC_REGISTRY[metric.name])


class TestEveryMetricIsQueryable(unittest.TestCase):
    """Every metric in the registry should compile on its own, with no
    dimensions/time grain, and project exactly its output_field."""

    def test_every_metric_compiles_alone(self) -> None:
        for name, metric in METRIC_REGISTRY.items():
            with self.subTest(metric=name):
                request = QueryRequest(metrics=(name,))
                compiled = build_query(request)

                self.assertEqual(compiled.output_columns, (metric.output_field,))
                self.assertIn(f"AS {metric.output_field}", compiled.sql)
                self.assertIn(f"FROM {metric.source_view}", compiled.sql)
                # No GROUP BY when no dimensions/time_grain requested.
                self.assertNotIn("GROUP BY", compiled.sql)

    def test_every_metric_supports_its_declared_dimensions(self) -> None:
        for name, metric in METRIC_REGISTRY.items():
            if not metric.supported_dimensions:
                continue
            with self.subTest(metric=name):
                request = QueryRequest(
                    metrics=(name,),
                    dimensions=(metric.supported_dimensions[0],),
                )
                compiled = build_query(request)
                self.assertIn(metric.supported_dimensions[0], compiled.sql)
                self.assertIn("GROUP BY", compiled.sql)

    def test_every_metric_supports_its_declared_time_grains(self) -> None:
        for name, metric in METRIC_REGISTRY.items():
            for grain in metric.supported_time_grains:
                with self.subTest(metric=name, grain=grain):
                    request = QueryRequest(metrics=(name,), time_grain=grain)
                    compiled = build_query(request)
                    self.assertIn("date_trunc(", compiled.sql)
                    self.assertIn("period", compiled.output_columns)

    def test_zero_if_no_data_wraps_in_coalesce(self) -> None:
        for name, metric in METRIC_REGISTRY.items():
            if not metric.zero_if_no_data:
                continue
            with self.subTest(metric=name):
                compiled = build_query(QueryRequest(metrics=(name,)))
                self.assertIn("COALESCE(", compiled.sql)


if __name__ == "__main__":
    unittest.main()
