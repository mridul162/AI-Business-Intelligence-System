from __future__ import annotations


from etl.pipelines.supplier_pipeline import SupplierPipeline


def main() -> None:

    pipeline = SupplierPipeline()

    result = pipeline.run()

    print("\nSupplier ETL pipeline completed successfully.")
    print(f"Ingestion Batch ID: {result.ingestion_batch_id}")
    print(f"Records Received: {result.records_received}")
    print(f"Records Loaded:   {result.records_loaded}")
    print(f"Records Rejected: {result.records_rejected}")


if __name__ == "__main__":
    main()