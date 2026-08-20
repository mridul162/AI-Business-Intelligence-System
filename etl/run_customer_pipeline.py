"""
Entry point for running the customer ETL pipeline.
"""

from etl.pipelines.customer_pipeline import CustomerPipeline


def main() -> None:
    pipeline = CustomerPipeline()

    result = pipeline.run()

    print("\nCustomer ETL pipeline completed successfully.")
    print(f"Ingestion Batch ID: {result.ingestion_batch_id}")
    print(f"Records Received: {result.records_received}")
    print(f"Records Loaded:   {result.records_loaded}")
    print(f"Records Rejected: {result.records_rejected}")


if __name__ == "__main__":
    main()