from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from etl.data_quality.models import DataQualityResult


def duplicate_count_check(
    session: Session,
    table_name: str,
    unique_column: str,
    expected_unique: bool = True,
) -> DataQualityResult:
    """Count duplicates in a business identifier column."""
    query = text(
        f"""
        SELECT COUNT(*)
        FROM (
            SELECT {unique_column}
            FROM {table_name}
            WHERE {unique_column} IS NOT NULL
            GROUP BY {unique_column}
            HAVING COUNT(*) > 1
        ) AS duplicates
        """
    )
    duplicate_count = int(session.execute(query).scalar_one() or 0)

    if duplicate_count == 0:
        return DataQualityResult(
            check_name=f"duplicate_count:{table_name}.{unique_column}",
            status="PASS",
            severity="INFO",
            message=f"No duplicate values found in '{table_name}.{unique_column}'.",
        )

    status = "FAIL" if expected_unique else "WARNING"
    severity = "ERROR" if expected_unique else "WARNING"

    return DataQualityResult(
        check_name=f"duplicate_count:{table_name}.{unique_column}",
        status=status,
        severity=severity,
        affected_rows=duplicate_count,
        message=(
            f"Found {duplicate_count} duplicate values in '{table_name}.{unique_column}'."
        ),
    )


def orphan_record_check(
    session: Session,
    child_table: str,
    child_fk_column: str,
    parent_table: str,
    parent_key_column: str,
) -> DataQualityResult:
    """Detect orphaned child records lacking a matching parent row."""
    query = text(
        f"""
        SELECT COUNT(*)
        FROM {child_table} AS c
        LEFT JOIN {parent_table} AS p
            ON c.{child_fk_column} = p.{parent_key_column}
        WHERE c.{child_fk_column} IS NOT NULL
          AND p.{parent_key_column} IS NULL
        """
    )
    orphan_count = int(session.execute(query).scalar_one() or 0)

    if orphan_count == 0:
        return DataQualityResult(
            check_name=f"orphan_check:{child_table}->{parent_table}",
            status="PASS",
            severity="INFO",
            message=(
                f"No orphaned rows found between '{child_table}.{child_fk_column}' "
                f"and '{parent_table}.{parent_key_column}'."
            ),
        )

    return DataQualityResult(
        check_name=f"orphan_check:{child_table}->{parent_table}",
        status="FAIL",
        severity="ERROR",
        affected_rows=orphan_count,
        message=(
            f"Found {orphan_count} orphaned rows in '{child_table}' where "
            f"'{child_fk_column}' has no matching parent in '{parent_table}'."
        ),
    )
