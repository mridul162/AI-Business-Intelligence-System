"""
Runner for loading the cash account dimension.
"""

from __future__ import annotations

from database.connection import session_scope
from etl.warehouse.dimensions.cash_account_dimension_loader import (
    CashAccountDimensionLoader,
)


def main() -> None:
    """Run the cash account dimension load."""

    with session_scope() as session:

        loader = CashAccountDimensionLoader(
            session=session,
        )
        records_loaded = loader.load()

    print(
        "\nCash account dimension load completed successfully."
    )
    print(
        f"Records Loaded: {records_loaded}"
    )


if __name__ == "__main__":
    main()