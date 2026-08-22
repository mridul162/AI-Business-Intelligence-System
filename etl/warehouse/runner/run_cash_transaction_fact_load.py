"""
Runner for loading the cash transactions fact table.
"""

from __future__ import annotations

from database.connection import session_scope

from etl.warehouse.facts.cash_transaction_fact_loader import (
    CashTransactionFactLoader,
)


def main() -> None:
    """Run the cash transaction fact table load."""

    with session_scope() as session:
        loader = CashTransactionFactLoader(
            session=session,
        )

        records_loaded = loader.load()

    print(
        "\nCash transaction fact load completed successfully."
    )
    print(
        f"Records Loaded/Updated: {records_loaded}"
    )


if __name__ == "__main__":
    main()