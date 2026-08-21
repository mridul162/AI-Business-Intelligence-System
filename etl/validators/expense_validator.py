"""
Validation logic for expense records.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from etl.models.validation import ValidationResult
from etl.validators.base import BaseValidator


class ExpenseValidator(BaseValidator):
    """Validate transformed expense records."""

    REQUIRED_FIELDS = (
        "expense_id",
        "expense_date",
        "amount",
    )

    def validate(
        self,
        record: dict[str, Any],
    ) -> ValidationResult:
        """Validate a single transformed expense record."""

        errors: list[str] = []

        self._validate_required_fields(
            record,
            errors,
        )

        self._validate_expense_date(
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
        """Validate required expense fields."""

        for field in ExpenseValidator.REQUIRED_FIELDS:
            value = record.get(field)

            if value is None or not str(value).strip():
                errors.append(
                    f"{field} is required."
                )

    @staticmethod
    def _validate_expense_date(
        record: dict[str, Any],
        errors: list[str],
    ) -> None:
        """Validate expense_date type when present."""

        expense_date = record.get("expense_date")

        if (
            expense_date is not None
            and not isinstance(expense_date, date)
        ):
            errors.append(
                "expense_date must be a valid date."
            )

    @staticmethod
    def _validate_amount(
        record: dict[str, Any],
        errors: list[str],
    ) -> None:
        """Validate amount type when present."""

        amount = record.get("amount")

        if (
            amount is not None
            and not isinstance(amount, Decimal)
        ):
            errors.append(
                "amount must be a valid decimal number."
            )