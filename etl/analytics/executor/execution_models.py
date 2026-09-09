"""
Data structures for the Query Executor package.

This module defines ONLY data -- see executor.py for how it gets
populated.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ExecutionResult:
    """
    The result of executing one BuiltQuery.statement.

    Attributes:
        columns: column names, in result order (from result.keys()).
        rows: one dict per row, keyed by column name, detached from
            the connection/cursor -- safe to hold onto after the
            connection that produced them has been closed. Values are
            whatever native Python types the driver/SQLAlchemy
            produced (Decimal, datetime, date, str, int, None, ...);
            nothing here reformats or stringifies them.
        row_count: len(rows). An empty result set (row_count == 0,
            rows == ()) is a successful, valid ExecutionResult, not
            an error.
        duration_seconds: wall-clock time for the connect+execute+
            fetch, measured with time.perf_counter(). Only present
            for a successful execution (an exception means no
            ExecutionResult is ever constructed).
    """

    columns: tuple[str, ...]
    rows: tuple[dict[str, Any], ...]
    row_count: int
    duration_seconds: float