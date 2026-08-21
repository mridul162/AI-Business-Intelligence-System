"""
Transformation logic for partner records.
"""

from __future__ import annotations

from typing import Any


class PartnerTransformer:
    """Transform raw partner records into staging-ready records."""

    SOURCE_SYSTEM = "HBMS"
    SOURCE_TABLE = "partners"

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
        """Transform one raw partner record."""

        return {
            "partner_id": self._clean_text(
                record.get("partner_id")
            ),
            "partner_name": self._clean_text(
                record.get("partner_name")
            ),
            # `role` is carried through for validation/logging even
            # though staging.stg_partners has no `role` column to
            # persist it into. PartnerLoader ignores this extra key.
            "role": self._clean_text(
                record.get("role")
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