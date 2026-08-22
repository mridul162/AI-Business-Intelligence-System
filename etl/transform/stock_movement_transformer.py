"""
Transformation logic for stock movement records.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any


class StockMovementTransformer:
    """Transform raw stock movement records into staging-ready records."""

    SOURCE_SYSTEM = "HBMS"
    SOURCE_TABLE = "expenses"

    DATE_FORMATS = (
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%m/%d/%Y",
        "%d/%m/%Y",
        "%d-%m-%Y",
    )

    TIMESTAMP_FORMATS = (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%a %b %d %Y %H:%M:%S GMT%z",
    )

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
    def _normalize_datetime_text(
        value: str,
    ) -> str:
        """Remove trailing timezone descriptions from JS-style dates."""

        if " (" in value:
            value = value.split(" (", 1)[0]

        return value.strip()

    @classmethod
    def _parse_date(
        cls,
        value: Any,
        field_name: str,
        errors: list[str],
    ) -> date | None:
        """Parse a date string using known formats."""

        text_value = cls._clean_text(value)

        if text_value is None:
            return None

        text_value = cls._normalize_datetime_text(
            text_value
        )

        for fmt in cls.DATE_FORMATS:
            try:
                return datetime.strptime(
                    text_value,
                    fmt,
                ).date()
            except ValueError:
                continue

        try:
            return datetime.strptime(
                text_value,
                "%a %b %d %Y %H:%M:%S GMT%z",
            ).date()
        except ValueError:
            pass

        errors.append(
            f"{field_name} could not be parsed as a date: "
            f"{text_value!r}"
        )

        return None

    @classmethod
    def _parse_timestamp(
        cls,
        value: Any,
        field_name: str,
        errors: list[str],
    ) -> datetime | None:
        """Parse a timestamp string using known formats."""

        text_value = cls._clean_text(value)

        if text_value is None:
            return None

        text_value = cls._normalize_datetime_text(
            text_value
        )

        for fmt in cls.TIMESTAMP_FORMATS:
            try:
                return datetime.strptime(
                    text_value,
                    fmt,
                )
            except ValueError:
                continue

        errors.append(
            f"{field_name} could not be parsed as a timestamp: "
            f"{text_value!r}"
        )

        return None

    @classmethod
    def _parse_quantity(
        cls,
        value: Any,
    ) -> Decimal | None:
        """
        Parse common numeric representations.

        Supports:
        123
        123.456
        1,234.5
        (12.5)  -> negative (accounting notation)
        """

        cleaned = cls._clean_text(value)

        if cleaned is None:
            return None

        negative = False

        if cleaned.startswith("(") and cleaned.endswith(")"):
            negative = True
            cleaned = cleaned[1:-1]

        cleaned = cleaned.replace(",", "").strip()

        if cleaned.startswith("-"):
            negative = True
            cleaned = cleaned[1:]

        try:
            quantity = Decimal(cleaned)
        except InvalidOperation as exc:
            raise ValueError(
                f"Unsupported quantity value: {value!r}"
            ) from exc

        return -quantity if negative else quantity

    def transform(
        self,
        record: dict[str, Any],
    ) -> dict[str, Any]:
        """Transform one raw stock movement record."""

        parse_errors: list[str] = []

        return {
            "movement_id": self._clean_text(
                record.get("movement_id")
            ),
            "movement_date": self._parse_date(
                record.get("movement_date"),
                "movement_date",
                parse_errors,
            ),
            "product_id": self._clean_text(
                record.get("product_id")
            ),
            "movement_type": self._clean_text(
                record.get("movement_type")
            ),
            "direction": self._clean_text(
                record.get("direction")
            ),
            "quantity": self._parse_quantity(
                record.get("quantity")
            ),
            "from_location_id": self._clean_text(
                record.get("from_location_id")
            ),
            "to_location_id": self._clean_text(
                record.get("to_location_id")
            ),
            "reference_id": self._clean_text(
                record.get("reference_id")
            ),
            "notes": self._clean_text(
                record.get("notes")
            ),
            "source_created_at": self._parse_timestamp(
                record.get("created_at"),
                "created_at",
                parse_errors
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