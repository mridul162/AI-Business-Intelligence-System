from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from etl.data_quality.models import DataQualityResult


def null_rate_check(
    session: Session,
    table_name: str,
    column_name: str,
    threshold: float = 0.0,
) -> DataQualityResult:
    """Measure null rate for a field and compare it against an allowed threshold."""
    total_query = text(f"SELECT COUNT(*) FROM {table_name}")
    total_rows = int(session.execute(total_query).scalar_one() or 0)

    if total_rows == 0:
        return DataQualityResult(
            check_name=f"null_rate:{table_name}.{column_name}",
            status="PASS",
            severity="INFO",
            message=f"No rows found in '{table_name}', so null rate is not applicable.",
        )

    null_query = text(
        f"SELECT COUNT(*) FROM {table_name} WHERE {column_name} IS NULL"
    )
    null_rows = int(session.execute(null_query).scalar_one() or 0)
    null_rate = (null_rows / total_rows) * 100.0

    if null_rate <= threshold:
        return DataQualityResult(
            check_name=f"null_rate:{table_name}.{column_name}",
            status="PASS",
            severity="INFO",
            message=(
                f"Null rate for '{table_name}.{column_name}' is {null_rate:.2f}% "
                f"(threshold: {threshold:.2f}%)."
            ),
        )

    return DataQualityResult(
        check_name=f"null_rate:{table_name}.{column_name}",
        status="WARNING",
        severity="WARNING",
        affected_rows=null_rows,
        message=(
            f"Null rate for '{table_name}.{column_name}' is {null_rate:.2f}% "
            f"which exceeds the threshold of {threshold:.2f}%."
        ),
    )
