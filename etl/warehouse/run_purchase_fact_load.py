"""
Runner for loading purchase facts into the warehouse.
"""

from __future__ import annotations

import logging

from database.connection import session_scope
from etl.warehouse.facts.purchase_fact_loader import (
    PurchaseFactLoader,
)


logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s | %(levelname)s | "
        "%(name)s | %(message)s"
    ),
)

logger = logging.getLogger(__name__)


def main() -> None:
    """Run the purchase fact warehouse load."""

    logger.info(
        "Starting purchase fact warehouse load."
    )

    with session_scope() as session:
        loader = PurchaseFactLoader(
            session=session,
        )

        records_loaded = loader.load()

    logger.info(
        "Purchase fact warehouse load completed. "
        "Records inserted or updated: %s",
        records_loaded,
    )

    print()
    print(
        "Purchase fact warehouse load "
        "completed successfully."
    )
    print(
        f"Records Loaded: {records_loaded}"
    )


if __name__ == "__main__":
    main()