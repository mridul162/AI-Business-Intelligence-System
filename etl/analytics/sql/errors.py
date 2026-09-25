"""
Exceptions raised while translating a QueryPlan into SQL.

One dedicated subclass per failure mode (per Milestone 3 requirements)
so callers can catch narrowly. Everything inherits from
SQLBuilderError so callers who don't care about the distinction can
catch just that.
"""

from __future__ import annotations


class SQLBuilderError(Exception):
    """Base class for all SQL-builder errors."""


class UnknownMetricError(SQLBuilderError):
    """A metric name in QueryPlan.metrics isn't in the registry."""


class SourceViewMismatchError(SQLBuilderError):
    """A metric's registry source_view doesn't match QueryPlan.source_view."""


class UnsupportedDimensionError(SQLBuilderError):
    """A requested dimension isn't supported by every metric in the plan."""


class UnsupportedTimeGrainError(SQLBuilderError):
    """The requested time_grain isn't supported by every metric in the plan."""


class UnsupportedFilterFieldError(SQLBuilderError):
    """A filter's field isn't supported by every metric in the plan."""


class UnsupportedFilterOperatorError(SQLBuilderError):
    """A filter's operator isn't in the builder's allowed operator set."""


class InvalidSortError(SQLBuilderError):
    """sort_by doesn't reference a column that will actually be selected."""


class InvalidLimitError(SQLBuilderError):
    """limit is not a positive integer."""


class InvalidQueryPlanError(SQLBuilderError):
    """
    The plan is structurally unusable by this builder -- e.g. no
    metrics, duplicate output fields that would collide in the
    SELECT list, or (defensively) metrics that disagree with each
    other in a way QueryPlan itself doesn't prevent.
    """


class MissingTimeColumnError(SQLBuilderError):
    """
    plan.time_grain or plan.time_range was set but this builder has
    no configured time column for plan.source_view. See
    sql_builder.TIME_COLUMN_BY_SOURCE_VIEW.
    """

class MissingTenantScopeError(SQLBuilderError):
    """
    No tenant scope was supplied and none could be resolved from request
    context. Raised only when require_tenant_scope=True, so callers that
    intentionally build unscoped queries (tests, admin/system tooling)
    are unaffected.
    """