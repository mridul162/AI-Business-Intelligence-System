"""
Run the warehouse load for return facts.
"""

from __future__ import annotations

import logging

from database.connection import session_scope
from etl.warehouse.facts.return_fact_loader import (
    ReturnFactLoader,
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
    """Run the return fact warehouse loader."""

    logger.info(
        "Starting return fact warehouse load."
    )

    with session_scope() as session:
        loader = ReturnFactLoader(
            session=session
        )

        records_loaded = loader.load()

    logger.info(
        "Return fact warehouse load completed. "
        "Records affected: %s",
        records_loaded,
    )

    print(
        "\nReturn fact warehouse load "
        "completed successfully."
    )
    print(
        f"Records Loaded/Updated: {records_loaded}"
    )


if __name__ == "__main__":
    main()