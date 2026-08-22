"""
Runner for loading the partner dimension.
"""

from __future__ import annotations

from database.connection import session_scope
from etl.warehouse.dimensions.partner_dimension_loader import (
    PartnerDimensionLoader,
)


def main() -> None:
    """Run the partner dimension load."""

    with session_scope() as session:

        loader = PartnerDimensionLoader(
            session=session,
        )
        records_loaded = loader.load()

    print(
        "\nPartner dimension load completed successfully."
    )
    print(
        f"Records Loaded: {records_loaded}"
    )


if __name__ == "__main__":
    main()