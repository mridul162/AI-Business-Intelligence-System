"""
Run the date dimension loader.
"""

from __future__ import annotations

from datetime import date

from database.connection import session_scope
from etl.warehouse.dimensions.date_dimension_loader import (
    DateDimensionLoader,
)


def main() -> None:
    """Populate core.dim_date for the configured date range."""

    start_date = date(2020, 1, 1)
    end_date = date(2035, 12, 31)

    with session_scope() as session:
        loader = DateDimensionLoader(
            session=session,
        )

        records_loaded = loader.load(
            start_date=start_date,
            end_date=end_date,
        )

    print("\nDate dimension load completed successfully.")
    print(f"Date Range:       {start_date} to {end_date}")
    print(f"Records Loaded:   {records_loaded}")


if __name__ == "__main__":
    main()