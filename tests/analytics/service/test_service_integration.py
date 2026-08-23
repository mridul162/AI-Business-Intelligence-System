"""End-to-end integration test for AnalyticalQueryService.

Unlike test_analytical_query_service.py (which mocks every stage to
isolate the orchestrator's sequencing/error-handling logic), this test
wires the service to the *real* AnalyticalQueryExecutor from
etl.analytics.execution.executor — the one stage in this pipeline that
already has a finished implementation. Only the semantic resolver,
query builder, and query validator are stubs, since
semantic_resolver.py, query/builder.py, and query/validator.py haven't
been shared yet.

This is what "review and test this existing AnalyticalQueryService
against the actual interfaces of all previously built layers" means in
practice: prove the service and the real executor actually fit
together (correct method names, correct CompiledQuery field usage,
correct psycopg2-style connection contract) rather than only proving
it against a MagicMock that would happily accept a call it got wrong.

The database itself is still faked — a fake psycopg2-style
connection/cursor, same technique as
tests/analytics/execution/test_executor.py — since there's no real
Postgres available in this environment. That fake is the only thing
standing in for "a real database."
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock

from etl.analytics.execution.executor import AnalyticalQueryExecutor
from etl.analytics.query.models import CompiledQuery, QueryRequest
from etl.analytics.service.analytical_query_service import (
    AnalyticalQueryService,
)


def make_fake_db_connection(*, fetchall_rows: list[tuple]) -> MagicMock:
    """Same fake psycopg2-style connection used in
    tests/analytics/execution/test_executor.py."""

    cursor = MagicMock()
    cursor.fetchall.return_value = fetchall_rows
    cursor.__enter__.return_value = cursor
    cursor.__exit__.return_value = False

    connection = MagicMock()
    connection.cursor.return_value = cursor
    return connection


class StubSemanticResolver:
    """Stands in for the real semantic_resolver.py (not yet shared)."""

    def __init__(self, request: QueryRequest) -> None:
        self._request = request
        self.received_text: list[str] = []

    def resolve(self, text: str) -> QueryRequest:
        self.received_text.append(text)
        return self._request


class StubQueryBuilder:
    """Stands in for the real query/builder.py (not yet shared)."""

    def __init__(self, compiled: CompiledQuery) -> None:
        self._compiled = compiled
        self.received_requests: list[QueryRequest] = []

    def build(self, request: QueryRequest) -> CompiledQuery:
        self.received_requests.append(request)
        return self._compiled


class PassthroughQueryValidator:
    """Stands in for the real query/validator.py (not yet shared)."""

    def __init__(self) -> None:
        self.received_queries: list[CompiledQuery] = []

    def validate(self, query: CompiledQuery) -> CompiledQuery:
        self.received_queries.append(query)
        return query


def build_service(
    *,
    request: QueryRequest,
    compiled: CompiledQuery,
    fetchall_rows: list[tuple],
) -> AnalyticalQueryService:
    connection = make_fake_db_connection(fetchall_rows=fetchall_rows)
    real_executor = AnalyticalQueryExecutor(connection)

    return AnalyticalQueryService(
        semantic_resolver=StubSemanticResolver(request),
        query_builder=StubQueryBuilder(compiled),
        query_validator=PassthroughQueryValidator(),
        executor=real_executor,
    )


class TestEndToEndWithRealExecutor:
    def test_full_pipeline_produces_correct_response(self) -> None:
        request = QueryRequest(metrics=("total_sales",), dimensions=("month",))
        compiled = CompiledQuery(
            sql="SELECT month, SUM(amount) AS total_sales "
            "FROM analytics.v_sales GROUP BY month",
            params={},
            output_columns=("month", "total_sales"),
        )
        service = build_service(
            request=request,
            compiled=compiled,
            fetchall_rows=[
                ("2026-08", Decimal("15990.00")),
                ("2026-09", Decimal("22000.00")),
            ],
        )

        response = service.query("total sales by month")

        assert response.success is True
        assert response.columns == ["month", "total_sales"]
        assert response.row_count == 2
        assert response.data == [
            {"month": "2026-08", "total_sales": 15990.0},
            {"month": "2026-09", "total_sales": 22000.0},
        ]
        assert response.query is request

    def test_empty_result_from_real_executor_is_still_a_success(self) -> None:
        request = QueryRequest(metrics=("total_sales",))
        compiled = CompiledQuery(
            sql="SELECT SUM(amount) AS total_sales FROM analytics.v_sales "
            "WHERE business_date >= %(start_date)s",
            params={"start_date": "2099-01-01"},
            output_columns=("total_sales",),
        )
        service = build_service(request=request, compiled=compiled, fetchall_rows=[])

        response = service.query("total sales next century")

        assert response.success is True
        assert response.row_count == 0
        assert response.data == []

    def test_real_executor_db_failure_surfaces_as_query_execution_stage(self) -> None:
        request = QueryRequest(metrics=("total_sales",))
        compiled = CompiledQuery(
            sql="SELECT SUM(amount) AS total_sales FROM analytics.v_sales",
            params={},
            output_columns=("total_sales",),
        )
        connection = make_fake_db_connection(fetchall_rows=[])
        connection.cursor.return_value.execute.side_effect = RuntimeError(
            "connection to server was lost"
        )
        service = AnalyticalQueryService(
            semantic_resolver=StubSemanticResolver(request),
            query_builder=StubQueryBuilder(compiled),
            query_validator=PassthroughQueryValidator(),
            executor=AnalyticalQueryExecutor(connection),
        )

        response = service.query("total sales")

        assert response.success is False
        assert response.error_stage == "query_execution"
        assert "connection to server was lost" in response.error

    def test_stages_receive_the_values_produced_by_the_previous_stage(self) -> None:
        """Proves wiring correctness, not just final output: each stub
        actually received what the previous real/stub stage produced."""

        request = QueryRequest(metrics=("total_purchases",))
        compiled = CompiledQuery(
            sql="SELECT SUM(line_total) AS total_purchases FROM analytics.v_purchases",
            params={},
            output_columns=("total_purchases",),
        )
        connection = make_fake_db_connection(
            fetchall_rows=[(Decimal("500.00"),)]
        )
        semantic_resolver = StubSemanticResolver(request)
        query_builder = StubQueryBuilder(compiled)
        query_validator = PassthroughQueryValidator()
        service = AnalyticalQueryService(
            semantic_resolver=semantic_resolver,
            query_builder=query_builder,
            query_validator=query_validator,
            executor=AnalyticalQueryExecutor(connection),
        )

        service.query("how much did we spend on purchases?")

        assert semantic_resolver.received_text == ["how much did we spend on purchases?"]
        assert query_builder.received_requests == [request]
        assert query_validator.received_queries == [compiled]
