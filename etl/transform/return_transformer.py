"""
Transformation logic for return records.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any


class ReturnTransformer:
    """Transform raw return records into staging-ready records."""

    SOURCE_SYSTEM = "HBMS"
    SOURCE_TABLE = "returns"

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
    def _parse_date(
        value: Any,
    ) -> date | None:
        """Parse supported HBMS date formats."""

        if value is None:
            return None

        value = str(value).strip()

        if not value:
            return None

        supported_formats = [
            "%Y-%m-%d",
            "%Y-%m-%d %H:%M:%S",
            "%d/%m/%Y",
            "%m/%d/%Y",
            "%a %b %d %Y %H:%M:%S GMT%z (%Z)",
        ]

        for date_format in supported_formats:
            try:
                return datetime.strptime(
                    value,
                    date_format,
                ).date()
            except ValueError:
                continue

        raise ValueError(
            f"Unsupported date format: {value!r}"
        )

    @staticmethod
    def _parse_datetime(
        value: Any,
    ) -> datetime | None:
        """Parse supported HBMS datetime formats."""

        if value is None:
            return None

        value = str(value).strip()

        if not value:
            return None

        supported_formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%a %b %d %Y %H:%M:%S GMT%z (%Z)",
        ]

        for date_format in supported_formats:
            try:
                return datetime.strptime(
                    value,
                    date_format,
                )
            except ValueError:
                continue

        raise ValueError(
            f"Unsupported datetime format: {value!r}"
        )

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
        """Transform one raw return record into a staging record."""

        return {
            "return_id": self._clean_text(
                record.get("return_id")
            ),
            "return_date": self._parse_date(
                record.get("return_date")
            ),
            # Not available in the current Returns source.
            "customer_id": None,
            "order_id": self._clean_text(
                record.get("reference_order_id")
            ),
            "total_amount": None,
            "refund_amount": self._parse_decimal(
                record.get("refund_amount")
            ),
            "adjustment_amount": None,
            "return_status": self._clean_text(
                record.get("status")
            ),
            "notes": self._clean_text(
                record.get("notes")
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
            "return_type": self._clean_text(
                record.get("return_type")
            ),
            "purchase_id": self._clean_text(
                record.get("reference_purchase_id")
            ),
            "location_id": self._clean_text(
                record.get("location_id")
            ),
            "cash_account_id": self._clean_text(
                record.get("cash_account_id")
            ),
            "returned_by": self._clean_text(
                record.get("returned_by")
            ),
            "reason": self._clean_text(
                record.get("reason")
            ),
            "source_created_at": self._parse_datetime(
                record.get("created_at")
            ),
        }