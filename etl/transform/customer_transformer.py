from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any


class CustomerTransformer:
    """Transform raw customer records into staging-ready records."""

    SOURCE_SYSTEM = "HBMS"
    SOURCE_TABLE = "customers"

    @staticmethod
    def _clean_text(value: Any) -> str | None:
        """Trim text and convert empty values to None."""
        if value is None:
            return None

        value = str(value).strip()

        return value or None

    @staticmethod
    def _parse_date(value: str | None) -> date | None:
        """Parse supported HBMS source date formats."""

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
    def _parse_int(value: Any) -> int | None:
        """Convert a source value into an integer."""
        if value is None:
            return None

        value = str(value).strip()

        if not value:
            return None

        return int(value)

    @staticmethod
    def _parse_decimal(value: Any) -> Decimal | None:
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
        """Transform one raw customer record into a staging record."""

        customer_id = self._clean_text(record.get("customer_id"))
        customer_name = self._clean_text(record.get("customer_name"))

        return {
            "customer_id": customer_id,
            "customer_name": customer_name,
            "contact": self._clean_text(record.get("contact")),
            "address": self._clean_text(record.get("address")),
            "first_order_date": self._parse_date(
                record.get("first_order_date")
            ),
            "last_order_date": self._parse_date(
                record.get("last_order_date")
            ),
            "total_orders": self._parse_int(
                record.get("total_orders")
            ),
            "total_spent": self._parse_decimal(
                record.get("total_spent")
            ),
            "total_paid": self._parse_decimal(
                record.get("total_paid")
            ),
            "total_due": self._parse_decimal(
                record.get("total_due")
            ),
            "status": self._clean_text(record.get("status")),
            "source_system": self.SOURCE_SYSTEM,
            "source_table": self.SOURCE_TABLE,
            "source_row_identifier": str(record["raw_id"]),
            "ingestion_batch_id": record["ingestion_batch_id"],
            "source_hash": record.get("source_row_hash"),
            "record_status": "pending",
            "validation_error": None,
        }