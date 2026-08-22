"""
Validation logic for warehouse dimensions.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass
class DimensionValidationResult:
    """Result of one dimension validation."""

    dimension_name: str
    expected_count: int
    actual_count: int
    duplicate_count: int

    @property
    def is_valid(self) -> bool:
        """Return whether the dimension validation passed."""

        return (
            self.expected_count == self.actual_count
            and self.duplicate_count == 0
        )


class DimensionValidator:
    """Validate warehouse dimension tables."""

    DIMENSIONS = (
        {
            "name": "dim_customer",
            "staging_table": "staging.stg_customers",
            "staging_id": "customer_id",
            "staging_key": "stg_customer_id",
            "core_table": "core.dim_customer",
            "core_id": "customer_id",
            "current_column": "active",
        },
        {
            "name": "dim_product",
            "staging_table": "staging.stg_products",
            "staging_id": "product_id",
            "staging_key": "stg_product_id",
            "core_table": "core.dim_product",
            "core_id": "product_id",
            "current_column": "is_current",
        },
        {
            "name": "dim_supplier",
            "staging_table": "staging.stg_suppliers",
            "staging_id": "supplier_id",
            "staging_key": "stg_supplier_id",
            "core_table": "core.dim_supplier",
            "core_id": "supplier_id",
            "current_column": "active",
        },
        {
            "name": "dim_partner",
            "staging_table": "staging.stg_partners",
            "staging_id": "partner_id",
            "staging_key": "stg_partner_id",
            "core_table": "core.dim_partner",
            "core_id": "partner_id",
            "current_column": "active",
        },
        {
            "name": "dim_cash_account",
            "staging_table": "staging.stg_cash_accounts",
            "staging_id": "cash_account_id",
            "staging_key": "stg_cash_account_id",
            "core_table": "core.dim_cash_account",
            "core_id": "cash_account_id",
            "current_column": "active",
        },
        {
            "name": "dim_location",
            "staging_table": "staging.stg_stock_locations",
            "staging_id": "stock_location_id",
            "staging_key": "stg_stock_location_id",
            "core_table": "core.dim_location",
            "core_id": "stock_location_id",
            "current_column": "active",
        },
    )

    def __init__(
        self,
        session: Session,
    ) -> None:
        self.session = session

    def validate_all(
        self,
    ) -> list[DimensionValidationResult]:
        """Validate all business dimensions."""

        return [
            self.validate_dimension(dimension)
            for dimension in self.DIMENSIONS
        ]

    def validate_dimension(
        self,
        dimension: dict[str, str],
    ) -> DimensionValidationResult:
        """Validate one dimension."""

        expected_count = self._get_expected_count(
            dimension
        )

        actual_count = self._get_actual_count(
            dimension
        )

        duplicate_count = self._get_duplicate_count(
            dimension
        )

        return DimensionValidationResult(
            dimension_name=dimension["name"],
            expected_count=expected_count,
            actual_count=actual_count,
            duplicate_count=duplicate_count,
        )

    def _get_expected_count(
        self,
        dimension: dict[str, str],
    ) -> int:
        """
        Count unique valid business identifiers
        available in staging.
        """

        query = text(
            f"""
            SELECT COUNT(DISTINCT {dimension["staging_id"]})
            FROM {dimension["staging_table"]}
            WHERE {dimension["staging_id"]} IS NOT NULL
              AND record_status <> 'rejected';
            """
        )

        result = self.session.execute(query)

        return result.scalar_one()

    def _get_actual_count(
        self,
        dimension: dict[str, str],
    ) -> int:
        """Count current warehouse dimension records."""

        query = text(
            f"""
            SELECT COUNT(*)
            FROM {dimension["core_table"]}
            WHERE {dimension["current_column"]} IS TRUE;
            """
        )

        result = self.session.execute(query)

        return result.scalar_one()

    def _get_duplicate_count(
        self,
        dimension: dict[str, str],
    ) -> int:
        """
        Count duplicate business identifiers among
        current warehouse records.
        """

        query = text(
            f"""
            SELECT COUNT(*)
            FROM (
                SELECT {dimension["core_id"]}
                FROM {dimension["core_table"]}
                WHERE {dimension["current_column"]} IS TRUE
                GROUP BY {dimension["core_id"]}
                HAVING COUNT(*) > 1
            ) AS duplicates;
            """
        )

        result = self.session.execute(query)

        return result.scalar_one()