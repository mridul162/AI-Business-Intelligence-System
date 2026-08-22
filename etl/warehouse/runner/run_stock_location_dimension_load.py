"""
Runner for loading the location dimension.
"""

from __future__ import annotations

from database.connection import session_scope
from etl.warehouse.dimensions.stock_location_dimension_loader import (
    LocationDimensionLoader,
)


def main() -> None:
    """Run the location dimension load."""

    with session_scope() as session:

        loader = LocationDimensionLoader(
            session=session,
        )
        records_loaded = loader.load()

    print(
        "\nLocation dimension load completed successfully."
    )
    print(
        f"Records Loaded: {records_loaded}"
    )


if __name__ == "__main__":
    main()