"""
Validation logic for customer records.

Validates transformed customer records before they are loaded into
staging.stg_customers.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any


class CustomerValidator:
    """
    Validate customer records against staging business requirements.
    """

    REQUIRED_FIELDS = (
        "customer_id",
        "customer_name",
    )

    def validate(self, record: dict[str, Any]) -> list[str]:
        """
        Validate a single transformed customer record.

        Returns:
            A list of validation error messages.
            An empty list means the record is valid.
        """
        errors: list[str] = []

        self._validate_required_fields(record, errors)
        self._validate_dates(record, errors)
        self._validate_numeric_fields(record, errors)
        self._validate_non_negative_values(record, errors)

        return errors

    def is_valid(self, record: dict[str, Any]) -> bool:
        """
        Return True if the record passes validation.
        """
        return not self.validate(record)

    @staticmethod
    def _validate_required_fields(
        record: dict[str, Any],
        errors: list[str],
    ) -> None:
        """
        Validate mandatory staging fields.
        """
        for field in CustomerValidator.REQUIRED_FIELDS:
            value = record.get(field)

            if value is None or not str(value).strip():
                errors.append(f"{field} is required.")

    @staticmethod
    def _validate_dates(
        record: dict[str, Any],
        errors: list[str],
    ) -> None:
        """
        Validate customer date fields and their logical ordering.
        """
        first_order_date = record.get("first_order_date")
        last_order_date = record.get("last_order_date")

        if (
            first_order_date is not None
            and not isinstance(first_order_date, date)
        ):
            errors.append(
                "first_order_date must be a valid date or None."
            )

        if (
            last_order_date is not None
            and not isinstance(last_order_date, date)
        ):
            errors.append(
                "last_order_date must be a valid date or None."
            )

        if (
            isinstance(first_order_date, date)
            and isinstance(last_order_date, date)
            and first_order_date > last_order_date
        ):
            errors.append(
                "first_order_date cannot be later than last_order_date."
            )

    @staticmethod
    def _validate_numeric_fields(
        record: dict[str, Any],
        errors: list[str],
    ) -> None:
        """
        Validate expected numeric field types.
        """
        total_orders = record.get("total_orders")

        if (
            total_orders is not None
            and (
                not isinstance(total_orders, int)
                or isinstance(total_orders, bool)
            )
        ):
            errors.append(
                "total_orders must be an integer or None."
            )

        monetary_fields = (
            "total_spent",
            "total_paid",
            "total_due",
        )

        for field in monetary_fields:
            value = record.get(field)

            if value is not None and not isinstance(value, Decimal):
                errors.append(
                    f"{field} must be a Decimal or None."
                )

    @staticmethod
    def _validate_non_negative_values(
        record: dict[str, Any],
        errors: list[str],
    ) -> None:
        """
        Validate fields that cannot contain negative values.
        """
        total_orders = record.get("total_orders")

        if isinstance(total_orders, int) and not isinstance(
            total_orders,
            bool,
        ):
            if total_orders < 0:
                errors.append(
                    "total_orders cannot be negative."
                )

        monetary_fields = (
            "total_spent",
            "total_paid",
            "total_due",
        )

        for field in monetary_fields:
            value = record.get(field)

            if isinstance(value, Decimal) and value < Decimal("0"):
                errors.append(
                    f"{field} cannot be negative."
                )