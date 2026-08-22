"""
Runner for loading the partner capital fact table.
"""

from __future__ import annotations

from database.connection import session_scope

from etl.warehouse.facts.partner_capital_fact_loader import (
    PartnerCapitalFactLoader,
)


def main() -> None:
    """Run the partner capital fact table load."""

    with session_scope() as session:
        loader = PartnerCapitalFactLoader(
            session=session,
        )

        records_loaded = loader.load()

    print(
        "\nPartner capital fact load completed successfully."
    )
    print(
        f"Records Loaded/Updated: {records_loaded}"
    )


if __name__ == "__main__":
    main()