"""
Validation logic for payment records.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from etl.models.validation import ValidationResult
from etl.validators.base import BaseValidator


class PaymentValidator(BaseValidator):
    """
    Validate transformed payment records.
    """

    REQUIRED_FIELDS = (
        "payment_id",
        "payment_date",
        "amount",
    )

    def validate(
        self,
        record: dict[str, Any],
    ) -> ValidationResult:
        """Validate one payment record."""

        errors: list[str] = []

        self._validate_required_fields(
            record,
            errors,
        )
        self._validate_types(
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
        """Return whether a payment record is valid."""

        return self.validate(record).is_valid

    @staticmethod
    def _validate_required_fields(
        record: dict[str, Any],
        errors: list[str],
    ) -> None:
        """Validate required fields."""

        for field in PaymentValidator.REQUIRED_FIELDS:
            value = record.get(field)

            if value is None:
                errors.append(
                    f"{field} is required."
                )
            elif isinstance(value, str) and not value.strip():
                errors.append(
                    f"{field} is required."
                )

    @staticmethod
    def _validate_types(
        record: dict[str, Any],
        errors: list[str],
    ) -> None:
        """Validate expected data types."""

        payment_date = record.get("payment_date")

        if (
            payment_date is not None
            and not isinstance(payment_date, date)
        ):
            errors.append(
                "payment_date must be a valid date."
            )

        amount = record.get("amount")

        if (
            amount is not None
            and not isinstance(amount, Decimal)
        ):
            errors.append(
                "amount must be a Decimal."
            )

    @staticmethod
    def _validate_amount(
        record: dict[str, Any],
        errors: list[str],
    ) -> None:
        """Validate payment amount."""

        amount = record.get("amount")

        if (
            isinstance(amount, Decimal)
            and amount <= Decimal("0")
        ):
            errors.append(
                "amount must be greater than zero."
            )