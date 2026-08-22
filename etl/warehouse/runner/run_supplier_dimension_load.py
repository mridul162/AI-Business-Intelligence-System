"""
Runner for loading the supplier dimension.
"""

from __future__ import annotations

from database.connection import session_scope
from etl.warehouse.dimensions.supplier_dimension_loader import (
    SupplierDimensionLoader,
)


def main() -> None:
    """Run the supplier dimension load."""

    with session_scope() as session:

        loader = SupplierDimensionLoader(
            session=session,
        )
        records_loaded = loader.load()

    print(
        "\nSupplier dimension load completed successfully."
    )
    print(
        f"Records Loaded: {records_loaded}"
    )


if __name__ == "__main__":
    main()