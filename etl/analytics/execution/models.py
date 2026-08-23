"""
Schemas for analytical query execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class QueryExecutionResult:
    """Result returned after executing an analytical query."""

    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
