"""
Run raw ingestion for HBMS Orders.csv.
"""

from __future__ import annotations

from pathlib import Path

from database.connection import session_scope

from etl.ingest.order_raw_ingestor import OrderRawIngestor


def main() -> None:
    csv_path = (
        Path("data")
        / "raw_exports"
        / "Orders.csv"
    )

    with session_scope() as session:
        ingestor = OrderRawIngestor(csv_path)

        result = ingestor.ingest(session)

    print("\nOrder raw ingestion completed successfully.")
    print(f"Ingestion Batch ID: {result.ingestion_batch_id}")
    print(f"Records Received:   {result.records_received}")
    print(f"Records Loaded:     {result.records_loaded}")
    print(f"Records Rejected:   {result.records_rejected}")


if __name__ == "__main__":
    main()