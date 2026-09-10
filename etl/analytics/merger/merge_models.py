"""
Data structures for the Result Merger package.

This module defines ONLY data. See result_merger.py for how
ExecutedQuery becomes MergedResult.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from etl.analytics.executor.execution_models import ExecutionResult
from etl.analytics.planner.query_plan import MergeStrategy
from etl.analytics.sql.sql_models import BuiltQuery


@dataclass(frozen=True)
class ExecutedQuery:
    """
    Pairs one QueryPlan's compiled statement with its execution
    result.

    This exists so the merger never has to reverse-engineer what a
    result's columns mean from the SQL statement itself --
    BuiltQuery already carries `plan`, `metric_output_fields`,
    `dimension_fields`, and `time_bucket_alias`, which is exactly the
    metadata row-alignment needs.
    """

    built_query: BuiltQuery
    result: ExecutionResult


@dataclass(frozen=True)
class MergedResult:
    """
    One canonical analytical result, produced by combining the
    ExecutionResults of every QueryPlan inside a MultiQueryPlan.

    Data-only, deliberately: no natural-language explanation, no
    business interpretation (e.g. no computed net_cash = cash_in -
    cash_out unless that's itself a registry metric), no formatting.
    That belongs to the layer above this one.

    Attributes:
        columns: grouping fields (dimensions, then the time bucket
            alias if present) followed by every query's metric
            output fields, in MultiQueryPlan.plans order.
        rows: one dict per grouping key that appeared in ANY of the
            merged queries, keyed by column name. A metric is 0 for
            a key when its query returned no row at all for that key
            (see result_merger.MISSING_METRIC_VALUE); it stays None
            when the query did return a row but the value itself was
            NULL. Native Python types (Decimal, date, datetime, ...)
            are preserved unchanged from the underlying
            ExecutionResults.
        row_count: len(rows). Zero merged queries producing rows is
            a valid, successful MergedResult, not an error.
        merge_strategy: copied from MultiQueryPlan.merge_strategy --
            recorded for the caller/answer layer, not interpreted
            here.
    """

    columns: tuple[str, ...]
    rows: tuple[dict[str, Any], ...]
    row_count: int
    merge_strategy: MergeStrategy