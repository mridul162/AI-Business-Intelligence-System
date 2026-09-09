"""
Data structures for the SQL Builder package.

This module defines ONLY data. It does not build SQL (clauses.py),
decide how to assemble it (sql_builder.py), or validate anything.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy.sql import Select

from etl.analytics.planner.query_plan import QueryPlan


@dataclass(frozen=True)
class BuiltQuery:
    """
    The result of translating one QueryPlan into a SQLAlchemy Core
    statement, plus enough metadata for a caller to make sense of the
    result set without re-deriving it from the plan.

    Attributes:
        statement: parameterized, not-yet-executed SQLAlchemy Select.
        plan: the QueryPlan this statement was built from (for
            logging/debugging -- not used by the executor).
        metric_output_fields: column labels for each metric, in the
            same order as plan.metrics.
        dimension_fields: column labels for each requested dimension,
            in the same order as plan.dimensions.
        time_bucket_alias: the label of the truncated-time column
            (e.g. "period"), or None if plan.time_grain was not set.
    """

    statement: Select
    plan: QueryPlan
    metric_output_fields: tuple[str, ...]
    dimension_fields: tuple[str, ...]
    time_bucket_alias: Optional[str]