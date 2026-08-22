"""
Runner for loading the sales fact table.
"""

from __future__ import annotations

from database.connection import session_scope

from etl.warehouse.facts.sales_fact_loader import (
    SalesFactLoader,
)


def main() -> None:
    """Run the sales fact table load."""

    with session_scope() as session:
        loader = SalesFactLoader(
            session=session,
        )

        records_loaded = loader.load()

    print(
        "\nSales fact load completed successfully."
    )
    print(
        f"Records Loaded/Updated: {records_loaded}"
    )


if __name__ == "__main__":
    main()