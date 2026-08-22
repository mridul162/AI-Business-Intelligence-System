"""
Runner for loading the stock movements fact table.
"""

from __future__ import annotations

from database.connection import session_scope

from etl.warehouse.facts.stock_movement_fact_loader import (
    StockMovementFactLoader,
)


def main() -> None:
    """Run the stock movement fact table load."""

    with session_scope() as session:
        loader = StockMovementFactLoader(
            session=session,
        )

        records_loaded = loader.load()

    print(
        "\nStock movement fact load completed successfully."
    )
    print(
        f"Records Loaded/Updated: {records_loaded}"
    )


if __name__ == "__main__":
    main()