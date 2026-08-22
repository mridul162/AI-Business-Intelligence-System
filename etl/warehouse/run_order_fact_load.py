"""
Runner for loading the orders fact table.
"""

from __future__ import annotations

from database.connection import session_scope

from etl.warehouse.facts.order_fact_loader import (
    OrderFactLoader,
)


def main() -> None:
    """Run the order fact table load."""

    with session_scope() as session:
        loader = OrderFactLoader(
            session=session,
        )

        records_loaded = loader.load()

    print(
        "\nOrder fact load completed successfully."
    )
    print(
        f"Records Loaded/Updated: {records_loaded}"
    )


if __name__ == "__main__":
    main()