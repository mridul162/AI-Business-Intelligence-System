from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from etl.data_quality.models import DataQualityResult


def sales_amount_rule_check(
    session: Session,
    table_name: str,
    quantity_column: str,
    unit_price_column: str,
    line_total_column: str,
    tolerance: float = 0.01,
) -> DataQualityResult:
    """Validate whether quantity × unit_price differs materially from line_total."""
    query = text(
        f"""
        SELECT COUNT(*)
        FROM {table_name}
        WHERE {quantity_column} IS NOT NULL
          AND {unit_price_column} IS NOT NULL
          AND {line_total_column} IS NOT NULL
          AND ABS(({quantity_column} * {unit_price_column}) - {line_total_column})
              > {tolerance}
        """
    )
    invalid_rows = int(session.execute(query).scalar_one() or 0)

    if invalid_rows == 0:
        return DataQualityResult(
            check_name=f"sales_amount_rule:{table_name}",
            status="PASS",
            severity="INFO",
            message=(
                f"All rows in '{table_name}' satisfy the quantity × unit_price ≈ line_total rule."
            ),
        )

    return DataQualityResult(
        check_name=f"sales_amount_rule:{table_name}",
        status="FAIL",
        severity="ERROR",
        affected_rows=invalid_rows,
        message=(
            f"Found {invalid_rows} rows in '{table_name}' where quantity × unit_price "
            f"does not match line_total within tolerance {tolerance}."
        ),
    )
