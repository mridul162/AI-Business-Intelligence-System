"""
Data structures for the Analytics Query Orchestrator.

This module defines ONLY data -- see analytics_orchestrator.py for
how ExecutionResult/MergedResult become AnalyticalResult.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from etl.analytics.executor.execution_models import ExecutionResult
from etl.analytics.merger.merge_models import MergedResult
from etl.analytics.planner.query_plan import MergeStrategy


@dataclass(frozen=True)
class AnalyticalResult:
    """
    One canonical result shape returned by
    AnalyticsQueryOrchestrator.execute(), regardless of whether the
    request resolved to a single QueryPlan or a MultiQueryPlan.

    This lets a caller consume the orchestrator's output without
    needing to know or care which path was taken internally.

    Attributes:
        columns: column names, in result order.
        rows: one dict per row, keyed by column name. Native Python
            types (Decimal, date, datetime, None, ...) are preserved
            unchanged from the underlying ExecutionResult/
            MergedResult -- nothing here reformats them.
        row_count: len(rows).
        merge_strategy: MergeStrategy.NONE for a single QueryPlan
            (this is exactly the case that member was reserved for --
            see MergeStrategy's docstring in query_plan.py), or the
            planner's actual chosen strategy for a MultiQueryPlan.
    """

    columns: tuple[str, ...]
    rows: tuple[dict[str, Any], ...]
    row_count: int
    merge_strategy: MergeStrategy

    @classmethod
    def from_execution_result(cls, result: ExecutionResult) -> "AnalyticalResult":
        """Normalize a single QueryPlan's ExecutionResult. No merge
        occurred, so merge_strategy is MergeStrategy.NONE."""
        return cls(
            columns=result.columns,
            rows=result.rows,
            row_count=result.row_count,
            merge_strategy=MergeStrategy.NONE,
        )

    @classmethod
    def from_merged_result(cls, result: MergedResult) -> "AnalyticalResult":
        """Normalize a MultiQueryPlan's MergedResult, carrying its
        merge_strategy through unchanged."""
        return cls(
            columns=result.columns,
            rows=result.rows,
            row_count=result.row_count,
            merge_strategy=result.merge_strategy,
        )