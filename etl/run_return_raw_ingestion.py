"""
Run raw ingestion for Returns.csv.
"""

from pathlib import Path

from etl.ingest.return_raw_ingestor import ReturnRawIngestor


def main() -> None:
    """Run the return raw ingestion process."""

    file_path = (
        Path("data")
        / "raw_exports"
        / "Returns.csv"
    )

    ingestor = ReturnRawIngestor(
        file_path=file_path,
    )

    result = ingestor.ingest()

    print("\nReturn raw ingestion completed successfully.")
    print(
        f"Ingestion Batch ID: {result.ingestion_batch_id}"
    )
    print(
        f"Records Received:   {result.records_received}"
    )
    print(
        f"Records Loaded:     {result.records_loaded}"
    )
    print(
        f"Records Rejected:   {result.records_rejected}"
    )


if __name__ == "__main__":
    main()