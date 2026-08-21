"""
Transformation logic for purchase records.

Unlike the supplier/partner transformers, several purchase fields
require type conversion (dates, timestamps, numerics) rather than
plain text cleanup. Parsing failures are not raised immediately;
instead they are collected into `_parse_errors` on the returned
record so PurchaseValidator can reject the record with a clear
message. `_parse_errors` is not a staging column and is ignored by
PurchaseLoader (extra keys in the params dict are simply unused).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any


class PurchaseTransformer:
    """Transform raw purchase records into staging-ready records."""

    SOURCE_SYSTEM = "HBMS"
    SOURCE_TABLE = "purchases"

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
    def _parse_decimal(
        cls,
        value: Any,
        field_name: str,
        errors: list[str],
    ) -> Decimal | None:
        """Parse a numeric string into a Decimal."""

        text_value = cls._clean_text(value)

        if text_value is None:
            return None

        normalized = (
            text_value
            .replace(",", "")
            .replace("$", "")
        )

        try:
            return Decimal(normalized)
        except InvalidOperation:
            errors.append(
                f"{field_name} could not be parsed as a number: "
                f"{text_value!r}"
            )

            return None

    def transform(
        self,
        record: dict[str, Any],
    ) -> dict[str, Any]:
        """Transform one raw purchase record."""

        parse_errors: list[str] = []

        purchase_date = self._parse_date(
            record.get("purchase_date"),
            "purchase_date",
            parse_errors,
        )

        source_created_at = self._parse_timestamp(
            record.get("created_at"),
            "created_at",
            parse_errors,
        )

        subtotal = self._parse_decimal(
            record.get("subtotal"),
            "subtotal",
            parse_errors,
        )

        discount = self._parse_decimal(
            record.get("discount"),
            "discount",
            parse_errors,
        )

        other_charges = self._parse_decimal(
            record.get("other_charges"),
            "other_charges",
            parse_errors,
        )

        total_amount = self._parse_decimal(
            record.get("total_amount"),
            "total_amount",
            parse_errors,
        )

        paid_amount = self._parse_decimal(
            record.get("paid"),
            "paid",
            parse_errors,
        )

        due_amount = self._parse_decimal(
            record.get("due"),
            "due",
            parse_errors,
        )

        return {
            "purchase_id": self._clean_text(
                record.get("purchase_id")
            ),
            "purchase_date": purchase_date,
            "supplier_id": self._clean_text(
                record.get("supplier_id")
            ),
            "subtotal": subtotal,
            "discount": discount,
            "other_charges": other_charges,
            "total_amount": total_amount,
            "paid_amount": paid_amount,
            "due_amount": due_amount,
            "payment_method": self._clean_text(
                record.get("payment_method")
            ),
            "cash_account_id": self._clean_text(
                record.get("cash_account_id")
            ),
            "purchased_by": self._clean_text(
                record.get("purchased_by")
            ),
            "purchase_status": self._clean_text(
                record.get("purchase_status")
            ),
            "notes": self._clean_text(
                record.get("notes")
            ),
            "source_created_at": source_created_at,
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
            "_parse_errors": parse_errors,
        }