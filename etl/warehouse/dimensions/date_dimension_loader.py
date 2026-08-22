"""
Loader for the core.dim_date warehouse dimension.
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session


class DateDimensionLoader:
    """
    Populate the core.dim_date dimension.

    The loader generates calendar attributes for every date in the
    specified range. Existing dates are skipped, making the loader
    safe to run multiple times.
    """

    INSERT_SQL = text(
        """
        INSERT INTO core.dim_date (
            date,
            year,
            quarter,
            month,
            month_number,
            month_name,
            week,
            day,
            day_name,
            is_weekend
        )
        VALUES (
            :date,
            :year,
            :quarter,
            :month,
            :month_number,
            :month_name,
            :week,
            :day,
            :day_name,
            :is_weekend
        )
        ON CONFLICT (date) DO NOTHING;
        """
    )

    def __init__(
        self,
        session: Session,
    ) -> None:
        self.session = session

    @staticmethod
    def _generate_date_record(
        current_date: date,
    ) -> dict[str, object]:
        """
        Generate dimension attributes for a single date.
        """

        return {
            "date": current_date,
            "year": current_date.year,
            "quarter": ((current_date.month - 1) // 3) + 1,
            "month": current_date.month,
            "month_number": current_date.month,
            "month_name": current_date.strftime("%B"),
            "week": current_date.isocalendar().week,
            "day": current_date.day,
            "day_name": current_date.strftime("%A"),
            "is_weekend": current_date.weekday() >= 5,
        }

    def load(
        self,
        start_date: date,
        end_date: date,
    ) -> int:
        """
        Populate core.dim_date for the specified date range.

        Existing dates are skipped.

        Args:
            start_date: First date to include.
            end_date: Last date to include.

        Returns:
            Number of newly inserted date records.
        """

        if start_date > end_date:
            raise ValueError(
                "start_date cannot be later than end_date."
            )

        records: list[dict[str, object]] = []

        current_date = start_date

        while current_date <= end_date:
            records.append(
                self._generate_date_record(
                    current_date
                )
            )

            current_date += timedelta(days=1)

        if not records:
            return 0

        result = self.session.execute(
            self.INSERT_SQL,
            records,
        )

        return int(getattr(result, "rowcount", 0) or 0)