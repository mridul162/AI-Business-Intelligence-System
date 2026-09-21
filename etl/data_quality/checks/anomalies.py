from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from etl.data_quality.models import DataQualityResult


def anomaly_threshold_check(
    session: Session,
    table_name: str,
    metric_column: str,
    lower_bound: float,
    upper_bound: float,
) -> DataQualityResult:
    """Flag rows outside a simple deterministic metric range."""
    query = text(
        f"""
        SELECT COUNT(*)
        FROM {table_name}
        WHERE {metric_column} IS NOT NULL
          AND ({metric_column} < :lower_bound OR {metric_column} > :upper_bound)
        """
    )
    invalid_rows = int(session.execute(query, {"lower_bound": lower_bound, "upper_bound": upper_bound}).scalar_one() or 0)

    if invalid_rows == 0:
        return DataQualityResult(
            check_name=f"anomaly_threshold:{table_name}.{metric_column}",
            status="PASS",
            severity="INFO",
            message=(
                f"No anomaly values were found for '{table_name}.{metric_column}' "
                f"outside [{lower_bound}, {upper_bound}]."
            ),
        )

    return DataQualityResult(
        check_name=f"anomaly_threshold:{table_name}.{metric_column}",
        status="WARNING",
        severity="WARNING",
        affected_rows=invalid_rows,
        message=(
            f"Found {invalid_rows} rows in '{table_name}.{metric_column}' "
            f"outside the allowed range [{lower_bound}, {upper_bound}]."
        ),
    )
