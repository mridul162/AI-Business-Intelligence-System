"""
Transformation logic for product records.

Converts raw product values from raw.products into properly typed,
staging-ready records for staging.stg_products.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any


class ProductTransformer:
    """Transform raw product records into staging-ready records."""

    SOURCE_SYSTEM = "HBMS"
    SOURCE_TABLE = "products"

    @staticmethod
    def _clean_text(value: Any) -> str | None:
        """Trim text and convert empty values to None."""
        if value is None:
            return None

        value = str(value).strip()

        return value or None

    @staticmethod
    def _parse_decimal(value: Any) -> Decimal | None:
        """
        Convert a source value into Decimal.

        Empty values are converted to None.
        """
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

    @staticmethod
    def _parse_boolean(value: Any) -> bool | None:
        """
        Convert supported source boolean values into Python bool.

        Supported true values:
            true, 1, yes, y, active

        Supported false values:
            false, 0, no, n, inactive
        """
        if value is None:
            return None

        normalized_value = str(value).strip().lower()

        if not normalized_value:
            return None

        true_values = {
            "true",
            "1",
            "yes",
            "y",
            "active",
        }

        false_values = {
            "false",
            "0",
            "no",
            "n",
            "inactive",
        }

        if normalized_value in true_values:
            return True

        if normalized_value in false_values:
            return False

        raise ValueError(
            f"Invalid boolean value: {value!r}"
        )

    def transform(
        self,
        record: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Transform one raw product record into a staging-ready record.
        """

        return {
            # ---------------------------------------------
            # Business fields
            # ---------------------------------------------
            "product_id": self._clean_text(
                record.get("product_id")
            ),
            "product_name": self._clean_text(
                record.get("product_name")
            ),
            "category": self._clean_text(
                record.get("category")
            ),
            "unit": self._clean_text(
                record.get("unit")
            ),
            "selling_price": self._parse_decimal(
                record.get("selling_price")
            ),
            "cost_price": self._parse_decimal(
                record.get("cost_price")
            ),
            "opening_stock": self._parse_decimal(
                record.get("opening_stock")
            ),
            "reorder_level": self._parse_decimal(
                record.get("reorder_level")
            ),
            "active": self._parse_boolean(
                record.get("active")
            ),

            # ---------------------------------------------
            # Data lineage
            # ---------------------------------------------
            "source_system": self.SOURCE_SYSTEM,
            "source_table": self.SOURCE_TABLE,
            "source_row_identifier": str(record["raw_id"]),
            "ingestion_batch_id": record["ingestion_batch_id"],
            "source_hash": record.get("source_row_hash"),

            # ---------------------------------------------
            # Processing status
            # ---------------------------------------------
            "record_status": "pending",
            "validation_error": None,
        }