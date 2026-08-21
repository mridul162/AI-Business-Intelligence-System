"""
Transformation logic for supplier records.
"""

from __future__ import annotations

from typing import Any


class SupplierTransformer:
    """Transform raw supplier records into staging-ready records."""

    SOURCE_SYSTEM = "HBMS"
    SOURCE_TABLE = "suppliers"

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
    def _parse_boolean(
        value: Any,
    ) -> bool | None:
        """
        Parse common boolean representations.

        Supports:
        True, False
        true, false
        yes, no
        1, 0
        active, inactive
        """

        if value is None:
            return None

        normalized = str(value).strip().lower()

        if not normalized:
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

        if normalized in true_values:
            return True

        if normalized in false_values:
            return False

        raise ValueError(
            f"Unsupported boolean value: {value!r}"
        )

    def transform(
        self,
        record: dict[str, Any],
    ) -> dict[str, Any]:
        """Transform one raw supplier record."""

        return {
            "supplier_id": self._clean_text(
                record.get("supplier_id")
            ),
            "supplier_name": self._clean_text(
                record.get("supplier_name")
            ),
            "contact": self._clean_text(
                record.get("contact")
            ),
            "address": self._clean_text(
                record.get("address")
            ),
            "active": self._parse_boolean(
                record.get("active")
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
