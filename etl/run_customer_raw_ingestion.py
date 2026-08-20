"""
Run customer CSV raw ingestion.

Flow:
    data/raw_exports/Customers.csv
        ↓
    CustomerRawIngestor
        ↓
    raw.ingestion_batches
        ↓
    raw.customers

Run from the project root:

    python -m etl.run_customer_raw_ingestion
"""

from __future__ import annotations

import logging
from pathlib import Path

from database.connection import session_scope

from etl.ingest.customer_raw_ingestor import CustomerRawIngestor


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)


def main() -> None:
    """Run customer raw CSV ingestion."""

    csv_path = (
        Path(__file__).resolve().parent.parent
        / "data"
        / "raw_exports"
        / "Customers.csv"
    )

    try:
        with session_scope() as session:
            ingestor = CustomerRawIngestor(
                session=session,
                csv_path=csv_path,
            )

            result = ingestor.ingest()

        print("\nCustomer raw ingestion completed successfully.")
        print(f"Ingestion Batch ID: {result.ingestion_batch_id}")
        print(f"Records Received:   {result.records_received}")
        print(f"Records Loaded:     {result.records_loaded}")
        print(f"Records Rejected:   {result.records_rejected}")

    except Exception as exc:
        logging.exception("Customer raw ingestion failed.")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()