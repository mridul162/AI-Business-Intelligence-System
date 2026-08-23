"""
End-to-end analytical query orchestration.

Ties together the components built in earlier phases into one usable
engine:

    natural language text
            |
            v
    SemanticResolver.resolve(text)   -> QueryRequest
            |
            v
    QueryBuilder.build(request)      -> CompiledQuery
            |
            v
    QueryValidator.validate(query)   -> CompiledQuery
            |
            v
    AnalyticalQueryExecutor.execute(query) -> QueryExecutionResult
            |
            v
    AnalyticalQueryResponse

This module intentionally does none of the actual work itself — no
parsing, no SQL building, no validation rules, no database access. It
only sequences calls to the injected components and turns whatever
happens (success or failure, at any stage) into one uniform response
shape. That is the whole point of an orchestration layer: callers
(an API route, an LLM tool, a CLI) get exactly one thing to deal with.
"""

from __future__ import annotations

from etl.analytics.execution.executor import AnalyticalQueryExecutor
from etl.analytics.service.errors import (
    QueryBuildError,
    QueryExecutionFailedError,
    QueryOrchestrationError,
    QueryValidationError,
    SemanticResolutionError,
)
from etl.analytics.service.interfaces import (
    QueryBuilder,
    QueryValidator,
    SemanticResolver,
)
from etl.analytics.service.models import AnalyticalQueryResponse


class AnalyticalQueryService:
    """Runs one natural-language analytical question through the
    full pipeline and returns a structured response.

    All dependencies are injected so this class stays testable without
    a real database or a real NL parser — see tests/analytics/service
    for examples using fakes/mocks for every stage.
    """

    def __init__(
        self,
        semantic_resolver: SemanticResolver,
        query_builder: QueryBuilder,
        query_validator: QueryValidator,
        executor: AnalyticalQueryExecutor,
    ) -> None:
        self.semantic_resolver = semantic_resolver
        self.query_builder = query_builder
        self.query_validator = query_validator
        self.executor = executor

    def query(self, text: str) -> AnalyticalQueryResponse:
        """Run `text` through the full pipeline.

        Never raises for expected pipeline failures (bad question,
        invalid query, execution error) — those come back as
        `AnalyticalQueryResponse(success=False, ...)` with the failing
        stage recorded in `error_stage`. Unexpected programming errors
        (e.g. a bug in one of the injected components that raises
        something unrelated to the pipeline) still propagate, since
        silently swallowing those would hide real bugs.
        """

        try:
            request = self._resolve_semantics(text)
            compiled = self._build_query(request)
            validated = self._validate_query(compiled)
            result = self._execute_query(validated)
        except QueryOrchestrationError as exc:
            return AnalyticalQueryResponse(
                success=False,
                error=str(exc),
                error_stage=exc.stage,
            )

        return AnalyticalQueryResponse(
            success=True,
            data=result.rows,
            row_count=result.row_count,
            columns=result.columns,
            query=request,
        )

    def _resolve_semantics(self, text: str):
        try:
            return self.semantic_resolver.resolve(text)
        except QueryOrchestrationError:
            raise
        except Exception as exc:
            raise SemanticResolutionError(str(exc)) from exc

    def _build_query(self, request):
        try:
            return self.query_builder.build(request)
        except QueryOrchestrationError:
            raise
        except Exception as exc:
            raise QueryBuildError(str(exc)) from exc

    def _validate_query(self, compiled):
        try:
            return self.query_validator.validate(compiled)
        except QueryOrchestrationError:
            raise
        except Exception as exc:
            raise QueryValidationError(str(exc)) from exc

    def _execute_query(self, compiled):
        try:
            return self.executor.execute(compiled)
        except QueryOrchestrationError:
            raise
        except Exception as exc:
            raise QueryExecutionFailedError(str(exc)) from exc
