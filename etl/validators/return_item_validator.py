"""
Validation logic for return item records.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from etl.models.validation import ValidationResult
from etl.validators.base import BaseValidator


class ReturnItemValidator(BaseValidator):
    """
    Validate return item records before loading into staging.
    """

    REQUIRED_FIELDS = (
        "return_item_id",
        "return_id",
        "product_id",
        "quantity",
    )

    def validate(
        self,
        record: dict[str, Any],
    ) -> ValidationResult:
        """Validate a single transformed return item record."""

        errors: list[str] = []

        self._validate_required_fields(
            record,
            errors,
        )

        self._validate_numeric_fields(
            record,
            errors,
        )

        self._validate_business_rules(
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
        """Validate mandatory fields."""

        for field in ReturnItemValidator.REQUIRED_FIELDS:
            value = record.get(field)

            if value is None or not str(value).strip():
                errors.append(
                    f"{field} is required."
                )

    @staticmethod
    def _validate_numeric_fields(
        record: dict[str, Any],
        errors: list[str],
    ) -> None:
        """Validate expected numeric field types."""

        numeric_fields = (
            "quantity",
            "unit_price",
            "amount",
        )

        for field in numeric_fields:
            value = record.get(field)

            if (
                value is not None
                and not isinstance(value, Decimal)
            ):
                errors.append(
                    f"{field} must be a Decimal or None."
                )

    @staticmethod
    def _validate_business_rules(
        record: dict[str, Any],
        errors: list[str],
    ) -> None:
        """Validate return item business rules."""

        quantity = record.get("quantity")

        if (
            isinstance(quantity, Decimal)
            and quantity <= Decimal("0")
        ):
            errors.append(
                "quantity must be greater than zero."
            )

        for field in (
            "unit_price",
            "amount",
        ):
            value = record.get(field)

            if (
                isinstance(value, Decimal)
                and value < Decimal("0")
            ):
                errors.append(
                    f"{field} cannot be negative."
                )