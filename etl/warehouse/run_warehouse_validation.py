"""
Run complete warehouse validation and reconciliation.
"""

from __future__ import annotations

import logging

from database.connection import session_scope

from etl.warehouse.validation.warehouse_validator import (
    WarehouseValidator,
)


logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s | %(levelname)s | "
        "%(name)s | %(message)s"
    ),
)

logger = logging.getLogger(__name__)


def print_separator() -> None:
    """Print a report separator."""

    print("-" * 80)


def main() -> None:
    """Run complete warehouse validation."""

    logger.info(
        "Starting warehouse validation."
    )

    with session_scope() as session:
        validator = WarehouseValidator(
            session=session,
        )

        report = validator.validate()

    print()
    print("=" * 80)
    print("WAREHOUSE VALIDATION REPORT")
    print("=" * 80)

    # --------------------------------------------------
    # Dimensions
    # --------------------------------------------------
    print()
    print("DIMENSION VALIDATION")
    print_separator()

    for result in report.dimensions:
        status = (
            "PASS"
            if result.is_valid
            else "FAIL"
        )

        print(
            f"{result.dimension_name:<30} "
            f"Expected: {result.expected_count:<8} "
            f"Actual: {result.actual_count:<8} "
            f"Duplicates: {result.duplicate_count:<5} "
            f"[{status}]"
        )

    # --------------------------------------------------
    # Facts
    # --------------------------------------------------
    print()
    print("FACT VALIDATION")
    print_separator()

    for result in report.facts:
        status = (
            "PASS"
            if result.is_valid
            else "FAIL"
        )

        print(
            f"{result.fact_name:<30} "
            f"Expected: {result.expected_count:<8} "
            f"Actual: {result.actual_count:<8} "
            f"Duplicates: {result.duplicate_count:<5} "
            f"[{status}]"
        )

    # --------------------------------------------------
    # Financial reconciliation
    # --------------------------------------------------
    print()
    print("FINANCIAL RECONCILIATION")
    print_separator()

    for result in report.reconciliations:
        status = (
            "PASS"
            if result.is_valid
            else "FAIL"
        )

        print(
            f"{result.metric_name:<30} "
            f"Source: {result.source_value:<15} "
            f"Warehouse: {result.warehouse_value:<15} "
            f"Difference: {result.difference:<15} "
            f"[{status}]"
        )

    # --------------------------------------------------
    # Final result
    # --------------------------------------------------
    print()
    print("=" * 80)

    if report.is_valid:
        print(
            "FINAL STATUS: PASS — "
            "Warehouse validation completed successfully."
        )
    else:
        print(
            "FINAL STATUS: FAIL — "
            "One or more validation checks failed."
        )

    print("=" * 80)

    logger.info(
        "Warehouse validation completed. "
        "Overall status: %s",
        "PASS" if report.is_valid else "FAIL",
    )


if __name__ == "__main__":
    main()