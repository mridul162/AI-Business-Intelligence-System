from __future__ import annotations

from datetime import date
from typing import cast

from unittest.mock import Mock

import pytest

from etl.analytics.application.analytics_application import AnalyticsApplication
from etl.analytics.orchestration import AnalyticalResult
from etl.analytics.planner.query_plan import MergeStrategy
from etl.analytics.response.builder import AnalyticalResponse
from etl.analytics.response.models import AnalyticalResponseStatus
from etl.analytics.schemas import AnalyticalQueryRequest
from etl.analytics.semantic import ResolvedAnalyticalQuery
from etl.observability.metrics import metrics

@pytest.fixture(autouse=True)
def reset_metrics():
    metrics.reset()
    yield
    metrics.reset()


def make_request() -> AnalyticalQueryRequest:
    return AnalyticalQueryRequest(
        metric="gross_sales",
        additional_metrics=(),
        dimensions=(),
        filters=(),
        time_grain=None,
        time_range=None,
        limit=None,
        sort_by=None,
        sort_order="asc",
        comparison=None,
        raw_question="What are my total sales?",
    )


def make_resolved_query(
    request: AnalyticalQueryRequest,
) -> ResolvedAnalyticalQuery:
    return ResolvedAnalyticalQuery(
        metric=request.metric,
        additional_metrics=request.additional_metrics,
        dimensions=request.dimensions,
        filters=(),
        time_grain=request.time_grain,
        time_range=request.time_range,
        limit=request.limit,
        sort_by=request.sort_by,
        sort_order=request.sort_order,
        comparison=request.comparison,
        raw_question=request.raw_question,
    )


def make_result(
    rows: tuple[dict, ...] = (),
    columns: tuple[str, ...] = (),
) -> AnalyticalResult:
    return AnalyticalResult(
        columns=columns,
        rows=rows,
        row_count=len(rows),
        merge_strategy=MergeStrategy.NONE,
    )


def make_response(
    *,
    status: AnalyticalResponseStatus = AnalyticalResponseStatus.SUCCESS,
    data: list[dict] | None = None,
) -> AnalyticalResponse:
    data = [] if data is None else data

    return AnalyticalResponse(
        success=True,
        status=status,
        query=Mock(),
        metadata=Mock(),
        data=data,
    )


class TestAnalyticsApplication:
    def setup_method(self) -> None:
        self.parser = Mock()
        self.semantic_resolver = Mock()
        self.time_resolver = Mock()
        self.query_orchestrator = Mock()
        self.response_builder = Mock()

        self.request = make_request()
        self.resolved_query = make_resolved_query(self.request)
        self.resolved_request = self.request

        self.result = make_result(
            rows=({"gross_sales": 1000},),
            columns=("gross_sales",),
        )
        self.response = make_response(
            data=[{"gross_sales": 1000}],
        )

        self.parser.parse.return_value = self.request
        self.semantic_resolver.resolve.return_value = self.resolved_query
        self.time_resolver.return_value = self.resolved_request
        self.query_orchestrator.execute.return_value = self.result
        self.response_builder.build.return_value = self.response

        self.application = AnalyticsApplication(
            parser=self.parser,
            semantic_resolver=self.semantic_resolver,
            query_orchestrator=self.query_orchestrator,
            response_builder=self.response_builder,
            time_resolver=self.time_resolver,
        )

    def test_query_returns_response_from_response_builder(self) -> None:
        result = self.application.query("What are my total sales?")

        assert result is self.response

    def test_query_passes_question_to_parser(self) -> None:
        question = "What are my total sales?"

        self.application.query(question)

        self.parser.parse.assert_called_once_with(question)

    def test_query_passes_parsed_request_to_semantic_resolver(self) -> None:
        self.application.query("What are my total sales?")

        self.semantic_resolver.resolve.assert_called_once_with(
            self.request
        )

    def test_query_uses_analytical_request_from_resolved_query(self) -> None:
        resolved_query = Mock(spec=ResolvedAnalyticalQuery)
        resolved_request = make_request()

        resolved_query.to_analytical_query_request.return_value = (
            resolved_request
        )

        self.semantic_resolver.resolve.return_value = resolved_query
        self.time_resolver.return_value = resolved_request

        self.application.query("What are my total sales?")

        resolved_query.to_analytical_query_request.assert_called_once_with()
        self.time_resolver.assert_called_once_with(
            resolved_request,
            today=None,
        )

    def test_query_resolves_time_before_orchestrating(self) -> None:
        self.application.query("What are my total sales?")

        assert self.time_resolver.call_count == 1
        assert self.query_orchestrator.execute.call_count == 1

        time_call_order = self.time_resolver.call_args
        orchestrator_call_order = self.query_orchestrator.execute.call_args

        assert time_call_order is not None
        assert orchestrator_call_order is not None

    def test_query_passes_resolved_request_to_orchestrator(self) -> None:
        self.application.query("What are my total sales?")

        self.query_orchestrator.execute.assert_called_once_with(
            self.resolved_request, tenant_scope=None
        )

    def test_query_passes_request_and_result_to_response_builder(
        self,
    ) -> None:
        self.application.query("What are my total sales?")

        self.response_builder.build.assert_called_once_with(
            self.resolved_request,
            self.result,
        )

    def test_today_is_forwarded_to_time_resolver(self) -> None:
        reference_date = date(2026, 8, 15)

        self.application.query(
            "What were my sales yesterday?",
            today=reference_date,
        )

        self.time_resolver.assert_called_once_with(
            self.request,
            today=reference_date,
        )

    def test_pipeline_dependencies_are_called_once(self) -> None:
        self.application.query("What are my total sales?")

        self.parser.parse.assert_called_once()
        self.semantic_resolver.resolve.assert_called_once()
        self.time_resolver.assert_called_once()
        self.query_orchestrator.execute.assert_called_once()
        self.response_builder.build.assert_called_once()

    def test_same_response_object_from_builder_is_returned(self) -> None:
        expected = self.response_builder.build.return_value

        actual = self.application.query("What are my total sales?")

        assert actual is expected

    def test_query_records_success_metrics(self) -> None:
        self.application.query("What are my total sales?")

        snapshot = metrics.snapshot()
        counters = cast(dict[str, int], snapshot["counters"])

        assert counters["analytics_queries_total"] == 1
        assert counters["analytics_queries_successful"] == 1
        assert counters.get("analytics_queries_failed", 0) == 0

        timings = cast(list[object], snapshot["timings"])
        assert len(timings) >= 1


class TestAnalyticsApplicationErrorPropagation:
    def test_parser_error_propagates(self) -> None:
        error = ValueError("invalid parser output")
        self.parser = Mock()
        self.parser.parse.side_effect = error

        application = AnalyticsApplication(
            parser=self.parser,
            semantic_resolver=Mock(),
            query_orchestrator=Mock(),
            response_builder=Mock(),
            time_resolver=Mock(),
        )

        try:
            application.query("invalid question")
        except ValueError as exc:
            assert exc is error
        else:
            raise AssertionError("Expected parser error to propagate")

    def test_semantic_error_propagates(self) -> None:
        error = ValueError("semantic resolution failed")
        request = make_request()

        parser = Mock()
        parser.parse.return_value = request

        semantic_resolver = Mock()
        semantic_resolver.resolve.side_effect = error

        application = AnalyticsApplication(
            parser=parser,
            semantic_resolver=semantic_resolver,
            query_orchestrator=Mock(),
            response_builder=Mock(),
            time_resolver=Mock(),
        )

        try:
            application.query("invalid metric")
        except ValueError as exc:
            assert exc is error
        else:
            raise AssertionError("Expected semantic error to propagate")

    def test_orchestrator_error_propagates(self) -> None:
        error = ValueError("query execution failed")
        request = make_request()
        resolved_query = make_resolved_query(request)
        resolved_request = request

        parser = Mock()
        parser.parse.return_value = request

        semantic_resolver = Mock()
        semantic_resolver.resolve.return_value = resolved_query

        time_resolver = Mock()
        time_resolver.return_value = resolved_request

        orchestrator = Mock()
        orchestrator.execute.side_effect = error

        application = AnalyticsApplication(
            parser=parser,
            semantic_resolver=semantic_resolver,
            query_orchestrator=orchestrator,
            response_builder=Mock(),
            time_resolver=time_resolver,
        )

        try:
            application.query("What are my sales?")
        except ValueError as exc:
            assert exc is error
        else:
            raise AssertionError("Expected orchestrator error to propagate")


    def test_parser_error_records_failure_metrics(self) -> None:
        error = ValueError("invalid parser output")

        parser = Mock()
        parser.parse.side_effect = error

        application = AnalyticsApplication(
            parser=parser,
            semantic_resolver=Mock(),
            query_orchestrator=Mock(),
            response_builder=Mock(),
            time_resolver=Mock(),
        )

        try:
            application.query("invalid question")
        except ValueError as exc:
            assert exc is error
        else:
            raise AssertionError("Expected parser error to propagate")

        snapshot = metrics.snapshot()
        counters = cast(dict[str, int], snapshot["counters"])

        assert counters["analytics_queries_total"] == 1
        assert counters["analytics_queries_failed"] == 1
        assert counters.get("analytics_queries_successful", 0) == 0