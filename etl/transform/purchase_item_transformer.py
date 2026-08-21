"""
Transformation logic for purchase item records.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any


class PurchaseItemTransformer:
    """Transform raw purchase item records into staging-ready records."""

    SOURCE_SYSTEM = "HBMS"
    SOURCE_TABLE = "purchase_items"

    @staticmethod
    def _clean_text(
        value: Any,
    ) -> str | None:
        """Trim text and convert empty values to None."""

        if value is None:
            return None

        value = str(value).strip()

        return value or None

    @staticmethod
    def _parse_decimal(
        value: Any,
    ) -> Decimal | None:
        """
        Parse a raw text value into a Decimal.

        Empty or missing values return None. Values that cannot be
        parsed as a number raise ValueError so the caller can decide
        how to record the failure.
        """

        if value is None:
            return None

        normalized = str(value).strip()

        if not normalized:
            return None

        try:
            return Decimal(normalized)
        except InvalidOperation as exc:
            raise ValueError(
                f"Unsupported decimal value: {value!r}"
            ) from exc

    def transform(
        self,
        record: dict[str, Any],
    ) -> dict[str, Any]:
        """Transform one raw purchase item record."""

        return {
            "purchase_item_id": self._clean_text(
                record.get("purchase_item_id")
            ),
            "purchase_id": self._clean_text(
                record.get("purchase_id")
            ),
            "product_id": self._clean_text(
                record.get("product_id")
            ),
            "stock_location_id": self._clean_text(
                record.get("stock_location_id")
            ),
            "quantity": self._parse_decimal(
                record.get("quantity")
            ),
            "unit_cost": self._parse_decimal(
                record.get("unit_cost")
            ),
            # raw.purchase_items.discount -> staging item_discount
            "item_discount": self._parse_decimal(
                record.get("discount")
            ),
            # raw.purchase_items.line_total -> staging line_amount
            "line_amount": self._parse_decimal(
                record.get("line_total")
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