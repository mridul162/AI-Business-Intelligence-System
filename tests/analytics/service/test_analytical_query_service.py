"""Unit tests for etl.analytics.service.analytical_query_service.

Every stage (semantic resolver, query builder, validator, executor)
is a mock/fake — this proves the *sequencing and error-handling* of
the orchestrator, independent of any real parser, SQL builder,
validator, or database.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from etl.analytics.execution.executor import AnalyticalQueryExecutionError
from etl.analytics.execution.models import QueryExecutionResult
from etl.analytics.query.models import CompiledQuery, QueryRequest
from etl.analytics.service.analytical_query_service import (
    AnalyticalQueryService,
)


def make_service(
    *,
    resolved_request: QueryRequest | None = None,
    compiled_query: CompiledQuery | None = None,
    validated_query: CompiledQuery | None = None,
    execution_result: QueryExecutionResult | None = None,
    resolve_side_effect=None,
    build_side_effect=None,
    validate_side_effect=None,
    execute_side_effect=None,
):
    """Wire up an AnalyticalQueryService with mock stages.

    Each stage returns its "happy path" default unless a side_effect
    (usually an exception) is supplied to force that stage to fail.
    """

    resolved_request = resolved_request or QueryRequest(metrics=("total_sales",))
    compiled_query = compiled_query or CompiledQuery(
        sql="SELECT SUM(amount) AS total_sales FROM sales",
        params={},
        output_columns=("total_sales",),
    )
    validated_query = validated_query or compiled_query
    execution_result = execution_result or QueryExecutionResult(
        columns=["total_sales"],
        rows=[{"total_sales": 15990.0}],
        row_count=1,
    )

    semantic_resolver = MagicMock()
    if resolve_side_effect is not None:
        semantic_resolver.resolve.side_effect = resolve_side_effect
    else:
        semantic_resolver.resolve.return_value = resolved_request

    query_builder = MagicMock()
    if build_side_effect is not None:
        query_builder.build.side_effect = build_side_effect
    else:
        query_builder.build.return_value = compiled_query

    query_validator = MagicMock()
    if validate_side_effect is not None:
        query_validator.validate.side_effect = validate_side_effect
    else:
        query_validator.validate.return_value = validated_query

    executor = MagicMock()
    if execute_side_effect is not None:
        executor.execute.side_effect = execute_side_effect
    else:
        executor.execute.return_value = execution_result

    service = AnalyticalQueryService(
        semantic_resolver=semantic_resolver,
        query_builder=query_builder,
        query_validator=query_validator,
        executor=executor,
    )
    return service, semantic_resolver, query_builder, query_validator, executor


class TestHappyPath:
    def test_runs_all_stages_in_order_with_correct_arguments(self) -> None:
        request = QueryRequest(metrics=("total_sales",))
        compiled = CompiledQuery(sql="SELECT 1", params={}, output_columns=("total_sales",))
        service, resolver, builder, validator, executor = make_service(
            resolved_request=request,
            compiled_query=compiled,
            validated_query=compiled,
        )

        service.query("What were total sales?")

        resolver.resolve.assert_called_once_with("What were total sales?")
        builder.build.assert_called_once_with(request)
        validator.validate.assert_called_once_with(compiled)
        executor.execute.assert_called_once_with(compiled)

    def test_returns_success_response_with_data_from_executor(self) -> None:
        execution_result = QueryExecutionResult(
            columns=["month", "total_sales"],
            rows=[
                {"month": "2026-08", "total_sales": 15990.0},
                {"month": "2026-09", "total_sales": 22000.0},
            ],
            row_count=2,
        )
        service, *_ = make_service(execution_result=execution_result)

        response = service.query("Show monthly sales.")

        assert response.success is True
        assert response.row_count == 2
        assert response.columns == ["month", "total_sales"]
        assert response.data == execution_result.rows
        assert response.error is None
        assert response.error_stage is None

    def test_response_carries_the_resolved_query_request(self) -> None:
        request = QueryRequest(metrics=("total_sales",), dimensions=("month",))
        service, *_ = make_service(resolved_request=request)

        response = service.query("total sales by month")

        assert response.query is request


class TestResponseToDict:
    def test_to_dict_summarizes_query_request(self) -> None:
        request = QueryRequest(metrics=("total_sales",), dimensions=("month",), limit=10)
        service, *_ = make_service(resolved_request=request)

        response = service.query("total sales by month")
        payload = response.to_dict()

        assert payload["success"] is True
        assert payload["query"] == {
            "metrics": ["total_sales"],
            "dimensions": ["month"],
            "limit": 10,
        }
        assert payload["row_count"] == response.row_count
        assert payload["data"] == response.data


class TestSemanticResolutionFailure:
    def test_unresolvable_question_returns_failure_response(self) -> None:
        service, *_ = make_service(
            resolve_side_effect=ValueError("unknown metric: 'foo'")
        )

        response = service.query("what is foo?")

        assert response.success is False
        assert response.error_stage == "semantic_resolution"
        assert "foo" in response.error
        assert response.data == []
        assert response.row_count == 0

    def test_does_not_call_downstream_stages(self) -> None:
        service, _, builder, validator, executor = make_service(
            resolve_side_effect=ValueError("nope")
        )

        service.query("what is foo?")

        builder.build.assert_not_called()
        validator.validate.assert_not_called()
        executor.execute.assert_not_called()


class TestQueryBuildFailure:
    def test_build_failure_returns_failure_response(self) -> None:
        service, *_ = make_service(
            build_side_effect=ValueError("cannot join across views")
        )

        response = service.query("total sales and total purchases")

        assert response.success is False
        assert response.error_stage == "query_building"

    def test_does_not_call_validator_or_executor(self) -> None:
        service, _, _, validator, executor = make_service(
            build_side_effect=ValueError("nope")
        )

        service.query("total sales")

        validator.validate.assert_not_called()
        executor.execute.assert_not_called()


class TestQueryValidationFailure:
    def test_validation_failure_returns_failure_response(self) -> None:
        service, *_ = make_service(
            validate_side_effect=ValueError("limit exceeds maximum")
        )

        response = service.query("total sales")

        assert response.success is False
        assert response.error_stage == "query_validation"

    def test_does_not_call_executor(self) -> None:
        service, *_, executor = make_service(
            validate_side_effect=ValueError("nope")
        )

        service.query("total sales")

        executor.execute.assert_not_called()


class TestExecutionFailure:
    def test_raw_execution_error_returns_failure_response(self) -> None:
        service, *_ = make_service(
            execute_side_effect=RuntimeError("connection refused")
        )

        response = service.query("total sales")

        assert response.success is False
        assert response.error_stage == "query_execution"
        assert "connection refused" in response.error

    def test_wrapped_analytical_execution_error_returns_failure_response(self) -> None:
        service, *_ = make_service(
            execute_side_effect=AnalyticalQueryExecutionError(
                "Failed to execute analytical query."
            )
        )

        response = service.query("total sales")

        assert response.success is False
        assert response.error_stage == "query_execution"
