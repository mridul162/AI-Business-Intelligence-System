"""
CLI entry point for the Product ETL pipeline.

Extracts product records from raw.products, transforms and validates them,
then loads valid records into staging.stg_products.
"""

from __future__ import annotations

from etl.pipelines.product_pipeline import ProductPipeline


def main() -> None:
    """Run the Product ETL pipeline."""

    pipeline = ProductPipeline()

    result = pipeline.run()

    print("\nProduct ETL pipeline completed successfully.")
    print(f"Ingestion Batch ID: {result.ingestion_batch_id}")
    print(f"Records Received: {result.records_received}")
    print(f"Records Loaded:   {result.records_loaded}")
    print(f"Records Rejected: {result.records_rejected}")


if __name__ == "__main__":
    main()