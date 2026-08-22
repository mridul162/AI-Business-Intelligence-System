"""
Run the return item ETL pipeline.
"""

from __future__ import annotations

from etl.pipelines.return_item_pipeline import (
    ReturnItemPipeline,
)


def main() -> None:
    """Execute the return item ETL pipeline."""

    pipeline = ReturnItemPipeline()

    result = pipeline.run()

    print("\nReturn item ETL pipeline completed successfully.")
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