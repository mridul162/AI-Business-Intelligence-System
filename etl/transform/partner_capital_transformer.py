"""
Transformation logic for partner capital records.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any


class PartnerCapitalTransformer:
    """Transform raw partner capital records into staging-ready records."""

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
    def _parse_amount(
        cls,
        value: Any,
    ) -> Decimal | None:
        """Parse a monetary amount, tolerating currency symbols/commas."""

        text_value = cls._clean_text(value)

        if text_value is None:
            return None

        normalized = (
            text_value
            .replace("$", "")
            .replace(",", "")
            .strip()
        )

        negative = False

        if normalized.startswith("(") and normalized.endswith(")"):
            negative = True
            normalized = normalized[1:-1]

        try:
            amount = Decimal(normalized)
        except InvalidOperation as exc:
            raise ValueError(
                f"Unsupported amount value: {value!r}"
            ) from exc

        if negative:
            amount = -amount

        return amount

    def transform(
        self,
        record: dict[str, Any],
    ) -> dict[str, Any]:
        """Transform one raw partner capital record."""

        capital_transaction_id = self._clean_text(
            record.get("capital_transaction_id")
        )

        cash_transaction_id = self._clean_text(
            record.get("cash_transaction_id")
        )

        # staging.stg_partner_capital.partner_capital_entry_id is the
        # canonical business identifier for the entry and is required
        # (NOT NULL), but the source CSV only ever populates
        # capital_transaction_id. cash_transaction_id is carried
        # through from raw in case a future/alternate source populates
        # capital entries via the cash-transaction side instead; when
        # present it is used as the fallback entry id.
        partner_capital_entry_id = (
            capital_transaction_id or cash_transaction_id
        )

        parse_errors: list[str] = []

        return {
            "partner_capital_entry_id": partner_capital_entry_id,
            "entry_date": self._parse_date(
                record.get("transaction_date"),
                "transaction_date",
                parse_errors,
            ),
            "partner_id": self._clean_text(
                record.get("partner_id")
            ),
            "transaction_type": self._clean_text(
                record.get("transaction_type")
            ),
            "amount": self._parse_amount(
                record.get("amount")
            ),
            "cash_account_id": self._clean_text(
                record.get("cash_account_id")
            ),
            "notes": self._clean_text(
                record.get("notes")
            ),
            "capital_transaction_id": capital_transaction_id,
            "reference_id": self._clean_text(
                record.get("reference_id")
            ),
            "created_by": self._clean_text(
                record.get("created_by")
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