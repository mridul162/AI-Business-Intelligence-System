"""
Transformation logic for order item records.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from etl.transform.base import BaseTransformer


class OrderItemTransformer(BaseTransformer):
    """Transform raw order item records into staging-ready records."""

    SOURCE_SYSTEM = "HBMS"
    SOURCE_TABLE = "order_items"

    @staticmethod
    def _clean_text(value: Any) -> str | None:
        """Trim text and convert empty values to None."""
        if value is None:
            return None

        value = str(value).strip()
        return value or None

    @staticmethod
    def _parse_decimal(value: Any) -> Decimal | None:
        """Convert source values into Decimal."""
        if value is None:
            return None

        value = str(value).strip()

        if not value:
            return None

        value = value.replace(",", "")

        try:
            return Decimal(value)
        except InvalidOperation as exc:
            raise ValueError(
                f"Invalid decimal value: {value!r}"
            ) from exc

    def transform(
        self,
        record: dict[str, Any],
        *args: Any,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Transform one raw order item record."""

        return {
            "order_item_id": self._clean_text(
                record.get("order_item_id")
            ),
            "order_id": self._clean_text(
                record.get("order_id")
            ),
            "product_id": self._clean_text(
                record.get("product_id")
            ),
            "stock_location_id": self._clean_text(
                record.get("fulfilled_from_location_id")
            ),
            "quantity": self._parse_decimal(
                record.get("quantity")
            ),
            "unit_price": self._parse_decimal(
                record.get("unit_price")
            ),
            "cost_price": self._parse_decimal(
                record.get("cost_price")
            ),
            "line_amount": self._parse_decimal(
                record.get("line_total")
            ),
            "item_discount": self._parse_decimal(
                record.get("discount")
            ),
            "cogs": self._parse_decimal(
                record.get("cogs")
            ),
            "source_system": self.SOURCE_SYSTEM,
            "source_table": self.SOURCE_TABLE,
            "source_row_identifier": str(record["raw_id"]),
            "ingestion_batch_id": record["ingestion_batch_id"],
            "source_hash": record.get("source_row_hash"),
            "record_status": "pending",
            "validation_error": None,
        }