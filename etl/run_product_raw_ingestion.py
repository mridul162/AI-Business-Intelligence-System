"""
CLI entry point for product raw ingestion.

Reads Products.csv and loads the source records into raw.products.
"""

from __future__ import annotations

from pathlib import Path

from etl.ingest.product_raw_ingestor import ProductRawIngestor


def main() -> None:
    """Run the product raw ingestion process."""

    csv_path = (
        Path(__file__).resolve().parent.parent
        / "data"
        / "raw_exports"
        / "Products.csv"
    )

    ingestor = ProductRawIngestor(csv_path=csv_path)

    result = ingestor.ingest()

    print("\nProduct raw ingestion completed successfully.")
    print(f"Ingestion Batch ID: {result.ingestion_batch_id}")
    print(f"Records Received:   {result.records_received}")
    print(f"Records Loaded:     {result.records_loaded}")
    print(f"Records Rejected:   {result.records_rejected}")


if __name__ == "__main__":
    main()