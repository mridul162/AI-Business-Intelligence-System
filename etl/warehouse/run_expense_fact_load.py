"""
Runner for loading the expenses fact table.
"""

from __future__ import annotations

from database.connection import session_scope

from etl.warehouse.facts.expense_fact_loader import (
    ExpenseFactLoader,
)


def main() -> None:
    """Run the expense fact table load."""

    with session_scope() as session:
        loader = ExpenseFactLoader(
            session=session,
        )

        records_loaded = loader.load()

    print(
        "\nExpense fact load completed successfully."
    )
    print(
        f"Records Loaded/Updated: {records_loaded}"
    )


if __name__ == "__main__":
    main()