"""
Runner for loading the return items fact table.
"""

from __future__ import annotations

from database.connection import session_scope

from etl.warehouse.facts.return_item_fact_loader import (
    ReturnItemFactLoader,
)


def main() -> None:
    """Run the return item fact table load."""

    with session_scope() as session:
        loader = ReturnItemFactLoader(
            session=session,
        )

        records_loaded = loader.load()

    print(
        "\nReturn item fact load completed successfully."
    )
    print(
        f"Records Loaded/Updated: {records_loaded}"
    )


if __name__ == "__main__":
    main()