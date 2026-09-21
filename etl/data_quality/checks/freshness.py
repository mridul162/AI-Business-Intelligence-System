from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

from etl.data_quality.models import DataQualityResult


def freshness_check(
    session: Session,
    table_name: str,
    timestamp_column: str,
    max_age_hours: float,
) -> DataQualityResult:
    """Check whether a dataset has been updated within the allowed age window."""
    query = text(
        f"""
        SELECT MAX({timestamp_column})
        FROM {table_name}
        WHERE {timestamp_column} IS NOT NULL
        """
    )
    latest_value = session.execute(query).scalar_one()

    if latest_value is None:
        return DataQualityResult(
            check_name=f"freshness:{table_name}",
            status="WARNING",
            severity="WARNING",
            affected_rows=1,
            message=f"No non-null '{timestamp_column}' values were found for '{table_name}'.",
        )

    if isinstance(latest_value, str):
        latest_value = datetime.fromisoformat(latest_value)

    age = datetime.utcnow() - latest_value
    if age <= timedelta(hours=max_age_hours):
        return DataQualityResult(
            check_name=f"freshness:{table_name}",
            status="PASS",
            severity="INFO",
            message=(
                f"'{table_name}' is fresh: latest value at {latest_value.isoformat()} "
                f"({age.total_seconds() / 3600:.2f} hours old)."
            ),
        )

    return DataQualityResult(
        check_name=f"freshness:{table_name}",
        status="WARNING",
        severity="WARNING",
        message=(
            f"'{table_name}' is stale: latest value at {latest_value.isoformat()} "
            f"({age.total_seconds() / 3600:.2f} hours old; threshold: {max_age_hours} hours)."
        ),
        affected_rows=1,
    )
