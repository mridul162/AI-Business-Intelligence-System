"""
Validation logic for cash account records.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from etl.models.validation import ValidationResult
from etl.validators.base import BaseValidator


class CashAccountValidator(BaseValidator):
    """Validate transformed cash account records."""

    REQUIRED_FIELDS = (
        "cash_account_id",
        "account_name",
    )

    def validate(
        self,
        record: dict[str, Any],
    ) -> ValidationResult:
        """Validate one transformed cash account record."""

        errors: list[str] = []

        self._validate_required_fields(
            record,
            errors,
        )
        self._validate_numeric_fields(
            record,
            errors,
        )
        self._validate_non_negative_values(
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
        """Return True when the record passes validation."""

        return self.validate(record).is_valid

    @staticmethod
    def _validate_required_fields(
        record: dict[str, Any],
        errors: list[str],
    ) -> None:
        for field in CashAccountValidator.REQUIRED_FIELDS:
            value = record.get(field)

            if value is None or not str(value).strip():
                errors.append(f"{field} is required.")

    @staticmethod
    def _validate_numeric_fields(
        record: dict[str, Any],
        errors: list[str],
    ) -> None:
        monetary_fields = (
            "total_in",
            "total_out",
            "current_balance",
        )

        for field in monetary_fields:
            value = record.get(field)

            if (
                value is not None
                and not isinstance(value, Decimal)
            ):
                errors.append(
                    f"{field} must be a Decimal or None."
                )

    @staticmethod
    def _validate_non_negative_values(
        record: dict[str, Any],
        errors: list[str],
    ) -> None:
        for field in ("total_in", "total_out"):
            value = record.get(field)

            if (
                isinstance(value, Decimal)
                and value < Decimal("0")
            ):
                errors.append(
                    f"{field} cannot be negative."
                )