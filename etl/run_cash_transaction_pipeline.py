from __future__ import annotations

from etl.pipelines.cash_account_pipeline import CashAccountPipeline
from etl.pipelines.cash_transaction_pipeline import (
    CashTransactionPipeline,
)


def main() -> None:
    """Execute the cash transaction ETL pipeline."""

    pipeline = CashTransactionPipeline()

    result = pipeline.run()

    print("\nCash transaction ETL pipeline completed successfully.")
    print(
        f"Ingestion Batch ID: {result.ingestion_batch_id}"
    )
    print(
        f"Records Received: {result.records_received}"
    )
    print(
        f"Records Loaded:   {result.records_loaded}"
    )
    print(
        f"Records Rejected: {result.records_rejected}"
    )


if __name__ == "__main__":
    main()