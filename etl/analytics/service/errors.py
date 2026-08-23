"""
Errors raised by the end-to-end orchestration layer.

Each stage of the pipeline can fail for its own reasons (a metric name
that doesn't resolve, a query that fails validation, a database error
during execution). Rather than let arbitrary exceptions bubble up
unlabeled, the service wraps whatever the underlying component raises
in one of these, tagged with the stage it came from. That tag is what
lets a future API layer (Phase 9.7/9.8) turn a failure into the right
HTTP status code or user-facing message without string-matching on
exception text.

If a stage already raises one of these (e.g. because the injected
component was built with orchestration in mind), the service does not
double-wrap it.
"""

from __future__ import annotations


class QueryOrchestrationError(Exception):
    """Base class for errors raised while running the pipeline end to end."""

    stage: str = "orchestration"


class SemanticResolutionError(QueryOrchestrationError):
    """Raised when natural language cannot be resolved into a QueryRequest."""

    stage = "semantic_resolution"


class QueryBuildError(QueryOrchestrationError):
    """Raised when a QueryRequest cannot be compiled into SQL."""

    stage = "query_building"


class QueryValidationError(QueryOrchestrationError):
    """Raised when a compiled query fails validation."""

    stage = "query_validation"


class QueryExecutionFailedError(QueryOrchestrationError):
    """Raised when a validated query fails to execute.

    Wraps whatever the executor raises — including a raw DBAPI/driver
    error if the injected AnalyticalQueryExecutor was built with
    raise_on_error=False (its default), and
    AnalyticalQueryExecutionError if it was built with
    raise_on_error=True. Either way this is what the orchestration
    layer surfaces, so callers only ever need to check `error_stage`.
    """

    stage = "query_execution"
