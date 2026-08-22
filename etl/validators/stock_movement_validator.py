"""
Validation logic for stock movement records.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from etl.models.validation import ValidationResult
from etl.validators.base import BaseValidator


class StockMovementValidator(BaseValidator):
    """Validate transformed stock movement records."""

    REQUIRED_FIELDS = (
        "movement_id",
        "movement_date",
        "product_id",
        "movement_type",
        "quantity",
    )

    def validate(
        self,
        record: dict[str, Any],
    ) -> ValidationResult:
        """Validate a single transformed stock movement record."""

        errors: list[str] = []

        self._validate_required_fields(
            record,
            errors,
        )

        self._validate_movement_date(
            record,
            errors,
        )

        self._validate_quantity(
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
        """Validate required stock movement fields."""

        for field in StockMovementValidator.REQUIRED_FIELDS:
            value = record.get(field)

            if value is None or not str(value).strip():
                errors.append(
                    f"{field} is required."
                )

    @staticmethod
    def _validate_movement_date(
        record: dict[str, Any],
        errors: list[str],
    ) -> None:
        """Validate movement_date type when present."""

        movement_date = record.get("movement_date")

        if (
            movement_date is not None
            and not isinstance(movement_date, date)
        ):
            errors.append(
                "movement_date must be a valid date."
            )

    @staticmethod
    def _validate_quantity(
        record: dict[str, Any],
        errors: list[str],
    ) -> None:
        """Validate quantity type when present."""

        quantity = record.get("quantity")

        if (
            quantity is not None
            and not isinstance(quantity, Decimal)
        ):
            errors.append(
                "quantity must be a valid decimal number."
            )