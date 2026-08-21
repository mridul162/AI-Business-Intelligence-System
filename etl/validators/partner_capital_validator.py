"""
Validation logic for partner capital records.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from etl.models.validation import ValidationResult
from etl.validators.base import BaseValidator


class PartnerCapitalValidator(BaseValidator):
    """Validate transformed partner capital records."""

    REQUIRED_FIELDS = (
        "partner_capital_entry_id",
        "entry_date",
        "partner_id",
        "transaction_type",
        "amount",
    )

    def validate(
        self,
        record: dict[str, Any],
    ) -> ValidationResult:
        """Validate a single transformed partner capital record."""

        errors: list[str] = []

        self._validate_required_fields(
            record,
            errors,
        )

        self._validate_entry_date(
            record,
            errors,
        )

        self._validate_amount(
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
    def _validate_required_fields(
        record: dict[str, Any],
        errors: list[str],
    ) -> None:
        """Validate required partner capital fields."""

        for field in PartnerCapitalValidator.REQUIRED_FIELDS:
            value = record.get(field)

            if value is None or (
                isinstance(value, str) and not value.strip()
            ):
                errors.append(
                    f"{field} is required."
                )

    @staticmethod
    def _validate_entry_date(
        record: dict[str, Any],
        errors: list[str],
    ) -> None:
        """Validate entry_date is a proper date when present."""

        entry_date = record.get("entry_date")

        if (
            entry_date is not None
            and not isinstance(entry_date, date)
        ):
            errors.append(
                "entry_date must be a valid date."
            )

    @staticmethod
    def _validate_amount(
        record: dict[str, Any],
        errors: list[str],
    ) -> None:
        """Validate amount is numeric when present."""

        amount = record.get("amount")

        if (
            amount is not None
            and not isinstance(amount, Decimal)
        ):
            errors.append(
                "amount must be a valid decimal number."
            )