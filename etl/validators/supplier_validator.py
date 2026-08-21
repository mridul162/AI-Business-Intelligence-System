"""
Validation logic for supplier records.
"""

from __future__ import annotations

from typing import Any

from etl.models.validation import ValidationResult
from etl.validators.base import BaseValidator


class SupplierValidator(BaseValidator):
    """Validate transformed supplier records."""

    REQUIRED_FIELDS = (
        "supplier_id",
        "supplier_name",
    )

    def validate(
        self,
        record: dict[str, Any],
    ) -> ValidationResult:
        """Validate a single transformed supplier record."""

        errors: list[str] = []

        self._validate_required_fields(
            record,
            errors,
        )

        self._validate_active(
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
        """Validate required supplier fields."""

        for field in SupplierValidator.REQUIRED_FIELDS:
            value = record.get(field)

            if value is None or not str(value).strip():
                errors.append(
                    f"{field} is required."
                )

    @staticmethod
    def _validate_active(
        record: dict[str, Any],
        errors: list[str],
    ) -> None:
        """Validate active when a value is present."""

        active = record.get("active")

        if (
            active is not None
            and not isinstance(active, bool)
        ):
            errors.append(
                "active must be a boolean or None."
            )