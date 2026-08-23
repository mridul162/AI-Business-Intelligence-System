"""
Interfaces for the components AnalyticalQueryService depends on.

These are Protocols, not base classes to inherit from — your existing
etl/analytics/semantic/semantic_resolver.py, query/builder.py, and
query/validator.py just need to already have matching methods; nothing
needs to import from here for typing to work.

IMPORTANT: these signatures are best-guess placeholders based on the
Phase 9 pipeline diagram (parse -> resolve semantics -> build -> validate),
since the real modules for these three stages haven't been shared yet
(only etl/analytics/query/models.py and the execution layer have).
Paste semantic_resolver.py / builder.py / validator.py and this file
(plus analytical_query_service.py) will get tightened to match their
actual method names and signatures exactly.
"""

from __future__ import annotations

from typing import Protocol

from etl.analytics.query.models import CompiledQuery, QueryRequest


class SemanticResolver(Protocol):
    """Turns a natural-language question into a declarative QueryRequest.

    Assumed to internally cover parsing, normalization, and metric /
    dimension / filter / time resolution (Phases 9.1–9.3) — i.e. this
    is the orchestrator's single entry point into "understand the
    question", however many sub-steps that takes on your end.
    """

    def resolve(self, text: str) -> QueryRequest: ...


class QueryBuilder(Protocol):
    """Compiles a QueryRequest into parameterized SQL."""

    def build(self, request: QueryRequest) -> CompiledQuery: ...


class QueryValidator(Protocol):
    """Validates a compiled query before it's allowed to run.

    Assumed to raise on invalid input and return the (possibly
    normalized) CompiledQuery on success — adjust to `-> None` here
    and in analytical_query_service.py if your validator doesn't
    return anything.
    """

    def validate(self, query: CompiledQuery) -> CompiledQuery: ...
