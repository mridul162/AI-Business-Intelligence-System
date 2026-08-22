"""
Runner for loading the payments fact table.
"""

from __future__ import annotations

from database.connection import session_scope

from etl.warehouse.facts.payment_fact_loader import (
    PaymentFactLoader,
)


def main() -> None:
    """Run the payment fact table load."""

    with session_scope() as session:
        loader = PaymentFactLoader(
            session=session,
        )

        records_loaded = loader.load()

    print(
        "\nPayment fact load completed successfully."
    )
    print(
        f"Records Loaded/Updated: {records_loaded}"
    )


if __name__ == "__main__":
    main()