"""
Validation logic for return records.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from etl.models.validation import ValidationResult
from etl.validators.base import BaseValidator


class ReturnValidator(BaseValidator):
    """Validate transformed return records."""

    REQUIRED_FIELDS = (
        "return_id",
        "return_date",
    )

    def validate(
        self,
        record: dict[str, Any],
    ) -> ValidationResult:
        """Validate a single transformed return record."""

        errors: list[str] = []

        self._validate_required_fields(
            record,
            errors,
        )
        self._validate_date_fields(
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

    @staticmethod
    def _validate_required_fields(
        record: dict[str, Any],
        errors: list[str],
    ) -> None:
        """Validate mandatory fields."""

        for field in ReturnValidator.REQUIRED_FIELDS:
            value = record.get(field)

            if value is None:
                errors.append(
                    f"{field} is required."
                )
                continue

            if isinstance(value, str) and not value.strip():
                errors.append(
                    f"{field} is required."
                )

    @staticmethod
    def _validate_date_fields(
        record: dict[str, Any],
        errors: list[str],
    ) -> None:
        """Validate return date type."""

        return_date = record.get("return_date")

        if (
            return_date is not None
            and not isinstance(return_date, date)
        ):
            errors.append(
                "return_date must be a valid date."
            )

    @staticmethod
    def _validate_numeric_fields(
        record: dict[str, Any],
        errors: list[str],
    ) -> None:
        """Validate monetary field types."""

        monetary_fields = (
            "refund_amount",
            "total_amount",
            "adjustment_amount",
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
        """Validate that monetary values are not negative."""

        monetary_fields = (
            "refund_amount",
            "total_amount",
            "adjustment_amount",
        )

        for field in monetary_fields:
            value = record.get(field)

            if (
                isinstance(value, Decimal)
                and value < Decimal("0")
            ):
                errors.append(
                    f"{field} cannot be negative."
                )