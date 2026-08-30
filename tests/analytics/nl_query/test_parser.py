"""
Phase 9.2 -- NLQueryParser tests.

No real LLM is called anywhere here: `complete` is always a fake
function returning canned text, exactly the seam the parser was
designed around. These tests cover the parser's actual job --
JSON extraction/validation/conversion plumbing -- not LLM quality.
"""

from __future__ import annotations

import json
import unittest
from datetime import date

from etl.analytics.metrics.registry import list_metrics
from etl.analytics.schemas import AnalyticalQueryRequest, NotResolvedError
from etl.analytics.nl_query import (
    CompletionRequest,
    InvalidQuestionError,
    LLMCallError,
    LLMResponseFormatError,
    LLMResponseValidationError,
    NLQueryParser,
    ParserConfig,
)


def _parser_returning(text: str) -> NLQueryParser:
    return NLQueryParser(complete=lambda system_prompt, question: text)


class TestHappyPath(unittest.TestCase):
    def test_minimal_request_parses(self) -> None:
        parser = _parser_returning('{"metric": "total_sales"}')
        req = parser.parse("What were total sales?")
        self.assertIsInstance(req, AnalyticalQueryRequest)
        self.assertEqual(req.metric, "total_sales")
        self.assertEqual(req.raw_question, "What were total sales?")

    def test_raw_question_is_the_caller_input_not_llm_text(self) -> None:
        # raw_question must be what the caller asked, not anything the
        # LLM echoed back -- the parser should ignore any such field.
        parser = _parser_returning(
            json.dumps({"metric": "total_sales", "raw_question": "something else"})
        )
        req = parser.parse("original question text")
        self.assertEqual(req.raw_question, "original question text")

    def test_full_example_from_roadmap_absolute_period(self) -> None:
        payload = {
            "metric": "total_sales",
            "additional_metrics": ["total_payments"],
            "time_grain": "monthly",
            "time_range": {"start": "2026-08-01", "end": "2026-08-31"},
        }
        parser = _parser_returning(json.dumps(payload))
        req = parser.parse("Show monthly sales and payments for August 2026")

        self.assertEqual(req.metric, "total_sales")
        self.assertEqual(req.additional_metrics, ("total_payments",))
        self.assertEqual(req.time_grain, "monthly")
        assert req.time_range is not None
        self.assertEqual(req.time_range.start, date(2026, 8, 1))
        self.assertEqual(req.time_range.end, date(2026, 8, 31))
        self.assertTrue(req.is_ready_for_query_layer())
        req.to_query_request()  # should not raise

    def test_full_example_from_roadmap_relative_preset(self) -> None:
        payload = {"metric": "total_sales", "time_range": {"preset": "current_month"}}
        parser = _parser_returning(json.dumps(payload))
        req = parser.parse("What were my total sales this month?")

        assert req.time_range is not None
        self.assertEqual(req.time_range.preset, "current_month")
        assert req.time_range is not None
        self.assertFalse(req.time_range.is_resolved)
        self.assertFalse(req.is_ready_for_query_layer())
        with self.assertRaises(NotResolvedError):
            req.to_query_request()

    def test_filters_and_sort_and_limit(self) -> None:
        payload = {
            "metric": "gross_sales",
            "dimensions": ["product_category"],
            "filters": [{"dimension": "product_category", "operator": "eq", "value": "Snacks"}],
            "sort_by": "gross_sales",
            "sort_order": "asc",
            "limit": 5,
        }
        parser = _parser_returning(json.dumps(payload))
        req = parser.parse("top snacks by sales")
        self.assertEqual(req.dimensions, ("product_category",))
        self.assertEqual(len(req.filters), 1)
        self.assertEqual(req.filters[0].operator, "eq")
        self.assertEqual(req.sort_by, "gross_sales")
        self.assertEqual(req.sort_order, "asc")
        self.assertEqual(req.limit, 5)

    def test_comparison_parses_but_is_not_query_ready(self) -> None:
        payload = {"metric": "gross_sales", "comparison": {"mode": "previous_period"}}
        parser = _parser_returning(json.dumps(payload))
        req = parser.parse("sales this month vs last month")
        assert req.comparison is not None
        self.assertEqual(req.comparison.mode, "previous_period")
        self.assertFalse(req.is_ready_for_query_layer())

    def test_canonical_metric_response_converts_to_request(self) -> None:
        payload = {
            "metric": "capital_invested",
            "additional_metrics": [],
            "dimensions": [],
            "filters": [],
            "time_grain": None,
            "time_range": None,
            "limit": None,
            "sort_by": None,
            "sort_order": None,
            "comparison": None,
        }

        req = _parser_returning(json.dumps(payload)).parse(
            "How much did investors invest in total?"
        )

        self.assertEqual(req.metric, "capital_invested")


class TestResponseCleanup(unittest.TestCase):
    def test_strips_json_code_fence(self) -> None:
        text = '```json\n{"metric": "total_sales"}\n```'
        req = _parser_returning(text).parse("q")
        self.assertEqual(req.metric, "total_sales")

    def test_strips_plain_code_fence(self) -> None:
        text = '```\n{"metric": "total_sales"}\n```'
        req = _parser_returning(text).parse("q")
        self.assertEqual(req.metric, "total_sales")

    def test_extracts_json_object_from_surrounding_prose(self) -> None:
        text = 'Sure! Here you go:\n{"metric": "total_sales"}\nHope that helps.'
        req = _parser_returning(text).parse("q")
        self.assertEqual(req.metric, "total_sales")


class TestErrorHandling(unittest.TestCase):
    def test_empty_question_rejected_before_calling_llm(self) -> None:
        calls = []

        def complete(system_prompt: str, question: str) -> str:
            calls.append(question)
            return '{"metric": "x"}'

        parser = NLQueryParser(complete=complete)
        with self.assertRaises(InvalidQuestionError):
            parser.parse("   ")
        self.assertEqual(calls, [])  # LLM never called

    def test_llm_call_exception_wrapped(self) -> None:
        def broken_complete(system_prompt: str, question: str) -> str:
            raise ConnectionError("boom")

        parser = NLQueryParser(complete=broken_complete)
        with self.assertRaises(LLMCallError):
            parser.parse("What were total sales?")

    def test_empty_response_raises_format_error(self) -> None:
        with self.assertRaises(LLMResponseFormatError):
            _parser_returning("").parse("q")

    def test_non_json_response_raises_format_error(self) -> None:
        with self.assertRaises(LLMResponseFormatError):
            _parser_returning("sorry, I can't help with that").parse("q")

    def test_json_array_instead_of_object_raises_format_error(self) -> None:
        with self.assertRaises(LLMResponseFormatError):
            _parser_returning("[1, 2, 3]").parse("q")

    def test_missing_metric_raises_validation_error(self) -> None:
        with self.assertRaises(LLMResponseValidationError):
            _parser_returning("{}").parse("q")

    def test_empty_metric_raises_validation_error(self) -> None:
        with self.assertRaises(LLMResponseValidationError):
            _parser_returning('{"metric": ""}').parse("q")

    def test_unknown_filter_operator_raises_validation_error(self) -> None:
        payload = {
            "metric": "gross_sales",
            "filters": [{"dimension": "product_category", "operator": "smells_like", "value": "x"}],
        }
        with self.assertRaises(LLMResponseValidationError):
            _parser_returning(json.dumps(payload)).parse("q")

    def test_filters_not_a_list_raises_validation_error(self) -> None:
        payload = {"metric": "gross_sales", "filters": "eq product_category Snacks"}
        with self.assertRaises(LLMResponseValidationError):
            _parser_returning(json.dumps(payload)).parse("q")

    def test_unknown_comparison_mode_raises_validation_error(self) -> None:
        payload = {"metric": "gross_sales", "comparison": {"mode": "vibes_based"}}
        with self.assertRaises(LLMResponseValidationError):
            _parser_returning(json.dumps(payload)).parse("q")

    def test_bad_time_range_date_raises_validation_error(self) -> None:
        payload = {"metric": "gross_sales", "time_range": {"start": "not-a-date"}}
        with self.assertRaises(LLMResponseValidationError):
            _parser_returning(json.dumps(payload)).parse("q")

    def test_bad_time_grain_raises_validation_error(self) -> None:
        payload = {"metric": "gross_sales", "time_grain": "biannual"}
        with self.assertRaises(LLMResponseValidationError):
            _parser_returning(json.dumps(payload)).parse("q")

    def test_preset_and_label_together_raises_validation_error(self) -> None:
        payload = {
            "metric": "gross_sales",
            "time_range": {"preset": "last_month", "label": "Eid week"},
        }
        with self.assertRaises(LLMResponseValidationError):
            _parser_returning(json.dumps(payload)).parse("q")


class TestParserDoesNotResolveOrValidateAgainstRegistry(unittest.TestCase):
    """The whole point of this phase boundary: the parser accepts any
    plausible-looking metric/dimension string and does not check it
    against the real metric registry. That check happens later."""

    def test_nonexistent_metric_name_still_parses_successfully(self) -> None:
        req = _parser_returning('{"metric": "definitely_not_a_real_metric"}').parse("q")
        self.assertEqual(req.metric, "definitely_not_a_real_metric")

    def test_nonexistent_dimension_still_parses_successfully(self) -> None:
        payload = {"metric": "gross_sales", "dimensions": ["not_a_real_dimension"]}
        req = _parser_returning(json.dumps(payload)).parse("q")
        self.assertEqual(req.dimensions, ("not_a_real_dimension",))


class TestParserConfigIsPromptOnly(unittest.TestCase):
    def test_config_hints_reach_the_system_prompt(self) -> None:
        captured = {}

        def complete(system_prompt: str, question: str) -> str:
            captured["system_prompt"] = system_prompt
            return '{"metric": "total_sales"}'

        from etl.analytics.nl_query import MetricHint

        config = ParserConfig(
            metric_hints=(MetricHint("total_sales", "Gross revenue from sales"),),
            dimension_hints=("customer_name",),
            today=date(2026, 8, 22),
        )
        NLQueryParser(complete=complete, config=config).parse("q")

        self.assertIn("total_sales", captured["system_prompt"])
        self.assertIn("customer_name", captured["system_prompt"])
        self.assertIn("2026-08-22", captured["system_prompt"])


class TestCompletionRequest(unittest.TestCase):
    def test_parser_passes_generated_schema_to_completion_request(self) -> None:
        captured = {}

        def complete(request: CompletionRequest) -> str:
            captured["request"] = request
            return '{"metric": "capital_invested"}'

        req = NLQueryParser(complete=complete).parse(
            "How much did investors invested in total?"
        )

        completion_request = captured["request"]
        self.assertIsInstance(completion_request, CompletionRequest)
        self.assertIn("capital_invested", completion_request.system_prompt)
        self.assertEqual(
            completion_request.response_schema["properties"]["metric"]["enum"],
            [definition.name for definition in list_metrics()],
        )
        self.assertIn(
            "capital_invested",
            completion_request.response_schema["properties"]["metric"]["enum"],
        )
        self.assertNotIn(
            "total_investment",
            completion_request.response_schema["properties"]["metric"]["enum"],
        )
        self.assertEqual(req.metric, "capital_invested")


if __name__ == "__main__":
    unittest.main()
