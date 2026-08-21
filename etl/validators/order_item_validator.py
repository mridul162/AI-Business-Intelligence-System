"""
Validation logic for order item records.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from etl.models.validation import ValidationResult
from etl.validators.base import BaseValidator


class OrderItemValidator(BaseValidator):
    """Validate transformed order item records."""

    REQUIRED_FIELDS = (
        "order_item_id",
        "order_id",
        "product_id",
        "quantity",
    )

    def validate(
        self,
        record: dict[str, Any],
    ) -> ValidationResult:
        """Validate a transformed order item record."""

        errors: list[str] = []

        self._validate_required_fields(record, errors)
        self._validate_numeric_fields(record, errors)
        self._validate_non_negative_values(record, errors)

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
        for field in OrderItemValidator.REQUIRED_FIELDS:
            value = record.get(field)

            if value is None or (
                isinstance(value, str)
                and not value.strip()
            ):
                errors.append(f"{field} is required.")

    @staticmethod
    def _validate_numeric_fields(
        record: dict[str, Any],
        errors: list[str],
    ) -> None:
        numeric_fields = (
            "quantity",
            "unit_price",
            "cost_price",
            "line_amount",
            "item_discount",
            "cogs",
        )

        for field in numeric_fields:
            value = record.get(field)

            if value is not None and not isinstance(
                value,
                Decimal,
            ):
                errors.append(
                    f"{field} must be a Decimal or None."
                )

    @staticmethod
    def _validate_non_negative_values(
        record: dict[str, Any],
        errors: list[str],
    ) -> None:
        non_negative_fields = (
            "quantity",
            "unit_price",
            "cost_price",
            "line_amount",
            "item_discount",
            "cogs",
        )

        for field in non_negative_fields:
            value = record.get(field)

            if isinstance(value, Decimal) and value < Decimal("0"):
                errors.append(
                    f"{field} cannot be negative."
                )