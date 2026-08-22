"""
Run the payment ETL pipeline.
"""

from __future__ import annotations

from etl.pipelines.payment_pipeline import PaymentPipeline


def main() -> None:
    pipeline = PaymentPipeline()

    result = pipeline.run()

    print("\nPayment ETL pipeline completed successfully.")
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