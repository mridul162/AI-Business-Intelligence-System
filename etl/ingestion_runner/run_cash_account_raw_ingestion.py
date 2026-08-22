from __future__ import annotations

from pathlib import Path

from database.connection import session_scope

from etl.ingest.cash_account_raw_ingestor import (
    CashAccountRawIngestor,
)


def main() -> None:
    """Run cash account raw ingestion."""

    csv_path = (
        Path("data")
        / "raw_exports"
        / "Cash_Accounts.csv"
    )

    with session_scope() as session:
        ingestor = CashAccountRawIngestor(
            session=session,
            csv_path=csv_path,
        )

        result = ingestor.ingest()

    print("\nCash account raw ingestion completed successfully.")
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