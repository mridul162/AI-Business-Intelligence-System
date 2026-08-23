"""Unit tests for etl.analytics.execution.serializer."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from etl.analytics.execution.serializer import (
    serialize_row,
    serialize_rows,
    serialize_value,
)


class TestSerializeValue:
    def test_decimal_becomes_float(self) -> None:
        assert serialize_value(Decimal("15990.50")) == 15990.50
        assert isinstance(serialize_value(Decimal("1")), float)

    def test_date_becomes_iso_string(self) -> None:
        assert serialize_value(date(2026, 8, 1)) == "2026-08-01"

    def test_datetime_becomes_iso_string(self) -> None:
        value = datetime(2026, 8, 1, 12, 30, 0)
        assert serialize_value(value) == value.isoformat()

    def test_uuid_becomes_string(self) -> None:
        value = UUID("12345678-1234-5678-1234-567812345678")
        assert serialize_value(value) == str(value)

    def test_normal_values_pass_through_unchanged(self) -> None:
        assert serialize_value("sales") == "sales"
        assert serialize_value(42) == 42
        assert serialize_value(True) is True
        assert serialize_value(None) is None


class TestSerializeRow:
    def test_serializes_all_fields_in_row(self) -> None:
        row = {
            "business_date": date(2026, 8, 1),
            "total_sales": Decimal("15990.00"),
            "region": "Dhaka",
        }
        assert serialize_row(row) == {
            "business_date": "2026-08-01",
            "total_sales": 15990.0,
            "region": "Dhaka",
        }


class TestSerializeRows:
    def test_serializes_list_of_rows(self) -> None:
        rows = [
            {"month": "2026-08", "total_sales": Decimal("15990.00")},
            {"month": "2026-09", "total_sales": Decimal("22000.00")},
        ]
        assert serialize_rows(rows) == [
            {"month": "2026-08", "total_sales": 15990.0},
            {"month": "2026-09", "total_sales": 22000.0},
        ]

    def test_empty_list_returns_empty_list(self) -> None:
        assert serialize_rows([]) == []
