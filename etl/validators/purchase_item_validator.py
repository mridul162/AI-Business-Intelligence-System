"""
Validation logic for purchase item records.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from etl.models.validation import ValidationResult
from etl.validators.base import BaseValidator


class PurchaseItemValidator(BaseValidator):
    """Validate transformed purchase item records."""

    REQUIRED_FIELDS = (
        "purchase_item_id",
        "purchase_id",
        "product_id",
    )

    # Present in staging as nullable numeric columns; when supplied
    # they must have been parsed into a Decimal by the transformer.
    OPTIONAL_DECIMAL_FIELDS = (
        "unit_cost",
        "item_discount",
        "line_amount",
    )

    def validate(
        self,
        record: dict[str, Any],
    ) -> ValidationResult:
        """Validate a single transformed purchase item record."""

        errors: list[str] = []

        self._validate_required_fields(
            record,
            errors,
        )

        self._validate_quantity(
            record,
            errors,
        )

        self._validate_optional_decimals(
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
        """Validate required purchase item text fields."""

        for field in PurchaseItemValidator.REQUIRED_FIELDS:
            value = record.get(field)

            if value is None or not str(value).strip():
                errors.append(
                    f"{field} is required."
                )

    @staticmethod
    def _validate_quantity(
        record: dict[str, Any],
        errors: list[str],
    ) -> None:
        """Validate that quantity is present and numeric."""

        quantity = record.get("quantity")

        if quantity is None:
            errors.append(
                "quantity is required."
            )
            return

        if not isinstance(quantity, Decimal):
            errors.append(
                "quantity must be a decimal value."
            )

    @staticmethod
    def _validate_optional_decimals(
        record: dict[str, Any],
        errors: list[str],
    ) -> None:
        """Validate optional numeric fields when present."""

        for field in PurchaseItemValidator.OPTIONAL_DECIMAL_FIELDS:
            value = record.get(field)

            if (
                value is not None
                and not isinstance(value, Decimal)
            ):
                errors.append(
                    f"{field} must be a decimal value or None."
                )