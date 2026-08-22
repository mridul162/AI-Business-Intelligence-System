"""
Runner for loading the customer dimension.
"""

from __future__ import annotations

from database.connection import session_scope
from etl.warehouse.dimensions.customer_dimension_loader import (
    CustomerDimensionLoader,
)


def main() -> None:
    """Run the customer dimension load."""

    with session_scope() as session:

        loader = CustomerDimensionLoader(
            session=session,
        )
        records_loaded = loader.load()

    print(
        "\nCustomer dimension load completed successfully."
    )
    print(
        f"Records Loaded: {records_loaded}"
    )


if __name__ == "__main__":
    main()