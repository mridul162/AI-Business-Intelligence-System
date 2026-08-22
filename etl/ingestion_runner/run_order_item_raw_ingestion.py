"""
Run raw ingestion for Order_Items.csv.
"""

from __future__ import annotations

from pathlib import Path

from database.connection import session_scope
from etl.ingest.order_item_raw_ingestor import OrderItemRawIngestor


def main() -> None:
    csv_path = (
        Path(__file__).resolve().parent.parent
        / "data"
        / "raw_exports"
        / "Order_Items.csv"
    )

    with session_scope() as session:
        ingestor = OrderItemRawIngestor(csv_path)
        result = ingestor.ingest(session)

    print("\nOrder item raw ingestion completed successfully.")
    print(f"Ingestion Batch ID: {result.ingestion_batch_id}")
    print(f"Records Received:   {result.records_received}")
    print(f"Records Loaded:     {result.records_loaded}")
    print(f"Records Rejected:   {result.records_rejected}")


if __name__ == "__main__":
    main()