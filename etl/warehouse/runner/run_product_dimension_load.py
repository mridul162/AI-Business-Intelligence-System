"""
Runner for loading the product dimension.
"""

from __future__ import annotations

from database.connection import session_scope
from etl.warehouse.dimensions.product_dimension_loader import (
    ProductDimensionLoader,
)


def main() -> None:
    """Run the product dimension load."""

    with session_scope() as session:

        loader = ProductDimensionLoader(
            session=session,
        )
        records_loaded = loader.load()

    print(
        "\nProduct dimension load completed successfully."
    )
    print(
        f"Records Loaded: {records_loaded}"
    )


if __name__ == "__main__":
    main()