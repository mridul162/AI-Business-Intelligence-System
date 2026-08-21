"""
Validation logic for purchase records.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from etl.models.validation import ValidationResult
from etl.validators.base import BaseValidator


class PurchaseValidator(BaseValidator):
    """Validate transformed purchase records."""

    REQUIRED_FIELDS = (
        "purchase_id",
        "purchase_date",
    )

    NUMERIC_FIELDS = (
        "subtotal",
        "discount",
        "other_charges",
        "total_amount",
        "paid_amount",
        "due_amount",
    )

    def validate(
        self,
        record: dict[str, Any],
    ) -> ValidationResult:
        """Validate a single transformed purchase record."""

        errors: list[str] = []

        self._validate_parse_errors(
            record,
            errors,
        )

        self._validate_required_fields(
            record,
            errors,
        )

        self._validate_purchase_date(
            record,
            errors,
        )

        self._validate_numeric_fields(
            record,
            errors,
        )

        self._validate_source_created_at(
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
    def _validate_parse_errors(
        record: dict[str, Any],
        errors: list[str],
    ) -> None:
        """Surface any type-conversion errors raised during transform."""

        parse_errors = record.get("_parse_errors") or []

        errors.extend(parse_errors)

    @staticmethod
    def _validate_required_fields(
        record: dict[str, Any],
        errors: list[str],
    ) -> None:
        """Validate required purchase fields."""

        for field in PurchaseValidator.REQUIRED_FIELDS:
            value = record.get(field)

            if value is None or (
                isinstance(value, str)
                and not value.strip()
            ):
                errors.append(
                    f"{field} is required."
                )

    @staticmethod
    def _validate_purchase_date(
        record: dict[str, Any],
        errors: list[str],
    ) -> None:
        """Validate purchase_date, when present, is a date."""

        purchase_date = record.get("purchase_date")

        if (
            purchase_date is not None
            and not isinstance(purchase_date, date)
        ):
            errors.append(
                "purchase_date must be a valid date."
            )

    @staticmethod
    def _validate_numeric_fields(
        record: dict[str, Any],
        errors: list[str],
    ) -> None:
        """Validate numeric fields, when present, are Decimal."""

        for field in PurchaseValidator.NUMERIC_FIELDS:
            value = record.get(field)

            if value is not None and not isinstance(
                value,
                Decimal,
            ):
                errors.append(
                    f"{field} must be a valid number."
                )

    @staticmethod
    def _validate_source_created_at(
        record: dict[str, Any],
        errors: list[str],
    ) -> None:
        """Validate source_created_at, when present, is a timestamp."""

        source_created_at = record.get("source_created_at")

        if (
            source_created_at is not None
            and not isinstance(source_created_at, datetime)
        ):
            errors.append(
                "created_at must be a valid timestamp."
            )