"""
Run the complete HBMS order ETL pipeline.
"""

from __future__ import annotations

from etl.pipelines.order_pipeline import OrderPipeline


def main() -> None:
    pipeline = OrderPipeline()

    result = pipeline.run()

    print("\nOrder ETL pipeline completed successfully.")
    print(f"Ingestion Batch ID: {result.ingestion_batch_id}")
    print(f"Records Received: {result.records_received}")
    print(f"Records Loaded:   {result.records_loaded}")
    print(f"Records Rejected: {result.records_rejected}")


if __name__ == "__main__":
    main()