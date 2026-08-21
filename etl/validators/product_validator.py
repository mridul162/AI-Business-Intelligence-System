"""
Validation logic for product records.

Validates transformed product records before they are loaded into
staging.stg_products.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from etl.models.validation import ValidationResult
from etl.validators.base import BaseValidator


class ProductValidator(BaseValidator):
    """
    Validate product records against staging business requirements.
    """

    REQUIRED_FIELDS = (
        "product_id",
        "product_name",
    )

    def validate(
        self,
        record: dict[str, Any],
    ) -> ValidationResult:
        """
        Validate a single transformed product record.

        Returns:
            ValidationResult containing the validation status and errors.
        """
        errors: list[str] = []

        self._validate_required_fields(record, errors)
        self._validate_numeric_fields(record, errors)
        self._validate_non_negative_values(record, errors)
        self._validate_boolean_field(record, errors)

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
        """Validate mandatory product fields."""
        for field in ProductValidator.REQUIRED_FIELDS:
            value = record.get(field)

            if value is None or not str(value).strip():
                errors.append(f"{field} is required.")

    @staticmethod
    def _validate_numeric_fields(
        record: dict[str, Any],
        errors: list[str],
    ) -> None:
        """Validate expected numeric field types."""
        numeric_fields = (
            "selling_price",
            "cost_price",
            "opening_stock",
            "reorder_level",
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
        """
        Validate numeric fields that cannot contain negative values.
        """
        numeric_fields = (
            "selling_price",
            "cost_price",
            "opening_stock",
            "reorder_level",
        )

        for field in numeric_fields:
            value = record.get(field)

            if isinstance(value, Decimal) and value < Decimal("0"):
                errors.append(
                    f"{field} cannot be negative."
                )

    @staticmethod
    def _validate_boolean_field(
        record: dict[str, Any],
        errors: list[str],
    ) -> None:
        """Validate the active field."""
        active = record.get("active")

        if active is not None and not isinstance(active, bool):
            errors.append(
                "active must be a boolean or None."
            )