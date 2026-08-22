"""
Run the Returns ETL pipeline.
"""

from etl.pipelines.return_pipeline import ReturnPipeline


def main() -> None:
    """Run the complete Returns ETL pipeline."""

    pipeline = ReturnPipeline()

    result = pipeline.run()

    print("\nReturn ETL pipeline completed successfully.")
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