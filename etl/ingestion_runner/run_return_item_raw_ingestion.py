"""
Run raw ingestion for return items.
"""

from __future__ import annotations

from database.connection import session_scope

from etl.ingest.return_item_raw_ingestor import (
    ReturnItemRawIngestor,
)


CSV_PATH = "data/raw_exports/Return_Items.csv"


def main() -> None:
    """Run return item raw ingestion."""

    with session_scope() as session:
        ingestor = ReturnItemRawIngestor(
            session=session,
            csv_path=CSV_PATH,
        )

        result = ingestor.ingest()

    print("\nReturn item raw ingestion completed successfully.")
    print(
        f"Ingestion Batch ID: {result['ingestion_batch_id']}"
    )
    print(
        f"Records Received:   {result['records_received']}"
    )
    print(
        f"Records Loaded:     {result['records_loaded']}"
    )
    print(
        f"Records Rejected:   {result['records_rejected']}"
    )


if __name__ == "__main__":
    main()