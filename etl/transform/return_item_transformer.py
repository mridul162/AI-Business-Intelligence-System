"""
Transformation logic for return item records.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from etl.transform.base import BaseTransformer


class ReturnItemTransformer(BaseTransformer):
    """
    Transform raw return item records into staging-ready records.
    """

    SOURCE_SYSTEM = "HBMS"
    SOURCE_TABLE = "return_items"

    @staticmethod
    def _clean_text(value: Any) -> str | None:
        """Trim text and convert empty values to None."""

        if value is None:
            return None

        value = str(value).strip()

        return value or None

    @staticmethod
    def _parse_decimal(
        value: Any,
    ) -> Decimal | None:
        """Convert a source value into Decimal."""

        if value is None:
            return None

        value = str(value).strip()

        if not value:
            return None

        try:
            return Decimal(value)
        except InvalidOperation as exc:
            raise ValueError(
                f"Invalid decimal value: {value!r}"
            ) from exc

    def transform(
        self,
        record: dict[str, Any],
    ) -> dict[str, Any]:
        """Transform one raw return item into a staging record."""

        return {
            "return_item_id": self._clean_text(
                record.get("return_item_id")
            ),
            "return_id": self._clean_text(
                record.get("return_id")
            ),
            # Source CSV does not currently contain Order_Item_ID.
            "order_item_id": None,
            "product_id": self._clean_text(
                record.get("product_id")
            ),
            "quantity": self._parse_decimal(
                record.get("quantity")
            ),
            "unit_price": self._parse_decimal(
                record.get("unit_price")
            ),
            "amount": self._parse_decimal(
                record.get("line_amount")
            ),
            "source_system": self.SOURCE_SYSTEM,
            "source_table": self.SOURCE_TABLE,
            "source_row_identifier": str(
                record["raw_id"]
            ),
            "ingestion_batch_id": record[
                "ingestion_batch_id"
            ],
            "source_hash": record.get(
                "source_row_hash"
            ),
            "record_status": "pending",
            "validation_error": None,
        }