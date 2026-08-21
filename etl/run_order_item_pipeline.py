"""
Run the order item ETL pipeline.
"""

from __future__ import annotations

from etl.pipelines.order_item_pipeline import OrderItemPipeline


def main() -> None:
    pipeline = OrderItemPipeline()
    result = pipeline.run()

    print("\nOrder item ETL pipeline completed successfully.")
    print(f"Ingestion Batch ID: {result.ingestion_batch_id}")
    print(f"Records Received: {result.records_received}")
    print(f"Records Loaded:   {result.records_loaded}")
    print(f"Records Rejected: {result.records_rejected}")


if __name__ == "__main__":
    main()