"""
Validation logic for order records.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from etl.models.validation import ValidationResult
from etl.validators.base import BaseValidator


class OrderValidator(BaseValidator):
    """Validate transformed order records."""

    REQUIRED_FIELDS = (
        "order_id",
        "order_date",
    )

    def validate(
        self,
        record: dict[str, Any],
    ) -> ValidationResult:
        """Validate a transformed order record."""
        errors: list[str] = []

        self._validate_required_fields(record, errors)
        self._validate_field_types(record, errors)
        self._validate_non_negative_values(record, errors)

        return ValidationResult(
            errors=errors
        )

    def is_valid(
        self,
        record: dict[str, Any],
    ) -> bool:
        """Return whether a record passes validation."""
        return self.validate(record).is_valid

    @staticmethod
    def _validate_required_fields(
        record: dict[str, Any],
        errors: list[str],
    ) -> None:
        for field in OrderValidator.REQUIRED_FIELDS:
            value = record.get(field)

            if value is None:
                errors.append(f"{field} is required.")

            elif isinstance(value, str) and not value.strip():
                errors.append(f"{field} is required.")

    @staticmethod
    def _validate_field_types(
        record: dict[str, Any],
        errors: list[str],
    ) -> None:
        order_date = record.get("order_date")

        if (
            order_date is not None
            and not isinstance(order_date, date)
        ):
            errors.append(
                "order_date must be a valid date."
            )

        source_created_at = record.get(
            "source_created_at"
        )

        if (
            source_created_at is not None
            and not isinstance(source_created_at, datetime)
        ):
            errors.append(
                "source_created_at must be a valid datetime or None."
            )

        monetary_fields = (
            "subtotal",
            "discount",
            "delivery_charge",
            "total_amount",
            "paid_amount",
            "due_amount",
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
        monetary_fields = (
            "subtotal",
            "discount",
            "delivery_charge",
            "total_amount",
            "paid_amount",
            "due_amount",
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