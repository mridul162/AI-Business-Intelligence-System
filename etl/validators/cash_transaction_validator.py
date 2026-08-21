"""
Validation logic for cash transaction records.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from etl.models.validation import ValidationResult
from etl.validators.base import BaseValidator


class CashTransactionValidator(BaseValidator):
    """Validate transformed cash transaction records."""

    REQUIRED_TEXT_FIELDS = (
        "transaction_id",
        "transaction_type",
    )

    def validate(
        self,
        record: dict[str, Any],
    ) -> ValidationResult:
        """Validate a single transformed cash transaction record."""

        errors: list[str] = []

        self._validate_required_text_fields(
            record,
            errors,
        )

        self._validate_transaction_date(
            record,
            errors,
        )

        self._validate_amount(
            record,
            errors,
        )

        self._validate_source_created_at(
            record,
            errors,
        )

        return ValidationResult(
            errors=errors
        )

    def is_valid(
        self,
        record: dict[str, Any],
    ) -> bool:
        """Return True if the record passes validation."""

        return self.validate(record).is_valid

    @staticmethod
    def _validate_required_text_fields(
        record: dict[str, Any],
        errors: list[str],
    ) -> None:
        """Validate required cash transaction text fields."""

        for field in CashTransactionValidator.REQUIRED_TEXT_FIELDS:
            value = record.get(field)

            if value is None or not str(value).strip():
                errors.append(
                    f"{field} is required."
                )

    @staticmethod
    def _validate_transaction_date(
        record: dict[str, Any],
        errors: list[str],
    ) -> None:
        """Validate that transaction_date is present and a date."""

        transaction_date = record.get("transaction_date")

        if transaction_date is None:
            errors.append(
                "transaction_date is required."
            )
            return

        if not isinstance(transaction_date, date):
            errors.append(
                "transaction_date must be a date value."
            )

    @staticmethod
    def _validate_amount(
        record: dict[str, Any],
        errors: list[str],
    ) -> None:
        """Validate that amount is present and numeric."""

        amount = record.get("amount")

        if amount is None:
            errors.append(
                "amount is required."
            )
            return

        if not isinstance(amount, Decimal):
            errors.append(
                "amount must be a decimal value."
            )

    @staticmethod
    def _validate_source_created_at(
        record: dict[str, Any],
        errors: list[str],
    ) -> None:
        """Validate source_created_at when a value is present."""

        source_created_at = record.get("source_created_at")

        if (
            source_created_at is not None
            and not isinstance(source_created_at, datetime)
        ):
            errors.append(
                "source_created_at must be a timestamp or None."
            )