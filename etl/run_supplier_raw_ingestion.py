from __future__ import annotations

from pathlib import Path

from database.connection import session_scope

from etl.ingest.supplier_raw_ingestor import (
    SupplierRawIngestor,
)


def main() -> None:
    """Run supplier raw ingestion."""

    csv_path = (
        Path("data")
        / "raw_exports"
        / "Suppliers.csv"
    )

    with session_scope() as session:
        ingestor = SupplierRawIngestor(
            session=session,
            csv_path=csv_path,
        )

        result = ingestor.ingest()

    print("\nSupplier raw ingestion completed successfully.")
    print(
        f"Ingestion Batch ID: "
        f"{result['ingestion_batch_id']}"
    )
    print(
        f"Records Received:   "
        f"{result['records_received']}"
    )
    print(
        f"Records Loaded:     "
        f"{result['records_loaded']}"
    )
    print(
        f"Records Rejected:   "
        f"{result['records_rejected']}"
    )


if __name__ == "__main__":
    main()