"""
Serialization helpers for analytical query results.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID


def serialize_value(
    value: Any,
) -> Any:
    """Convert database values into JSON-compatible values."""

    if isinstance(value, Decimal):
        return float(value)

    if isinstance(value, (date, datetime)):
        return value.isoformat()

    if isinstance(value, UUID):
        return str(value)

    return value


def serialize_row(
    row: dict[str, Any],
) -> dict[str, Any]:
    """Serialize one analytical result row."""

    return {
        key: serialize_value(value)
        for key, value in row.items()
    }


def serialize_rows(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Serialize analytical result rows."""

    return [
        serialize_row(row)
        for row in rows
    ]
