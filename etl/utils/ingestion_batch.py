"""
Utilities for managing ETL ingestion batches.

Each ETL pipeline run creates an ingestion batch in
raw.ingestion_batches. The batch tracks:

- source information
- pipeline execution status
- record counts
- completion time
- failure details

The ingestion_batch_id provides lineage between raw and staging records
processed during the same pipeline run.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session


def create_ingestion_batch(
    session: Session,
    *,
    source_system: str,
    source_type: str,
    source_reference: str | None = None,
) -> UUID:
    """
    Create a new ingestion batch.

    A batch is created when an ETL pipeline starts. Its status is initially
    set to 'running'.

    Args:
        session: Active SQLAlchemy database session.
        source_system: Name of the source system, e.g. 'HBMS'.
        source_type: Type of source, e.g. 'google_sheets', 'database', or 'api'.
        source_reference: Optional reference identifying the source being ingested,
            e.g. spreadsheet ID, table name, or source URL.

    Returns:
        UUID of the newly created ingestion batch.
    """
    result = session.execute(
        text(
            """
            INSERT INTO raw.ingestion_batches (
                source_system,
                source_type,
                source_reference,
                status
            )
            VALUES (
                :source_system,
                :source_type,
                :source_reference,
                'running'
            )
            RETURNING ingestion_batch_id;
            """
        ),
        {
            "source_system": source_system,
            "source_type": source_type,
            "source_reference": source_reference,
        },
    )

    return result.scalar_one()


def mark_batch_completed(
    session: Session,
    *,
    ingestion_batch_id: UUID,
    records_received: int,
    records_loaded: int,
    records_rejected: int,
) -> None:
    """
    Mark an ingestion batch as successfully completed.

    Args:
        session: Active SQLAlchemy database session.
        ingestion_batch_id: ID of the ingestion batch.
        records_received: Total number of records extracted from the source.
        records_loaded: Number of successfully loaded records.
        records_rejected: Number of rejected or invalid records.
    """
    session.execute(
        text(
            """
            UPDATE raw.ingestion_batches
            SET
                status = 'completed',
                completed_at = NOW(),
                records_received = :records_received,
                records_loaded = :records_loaded,
                records_rejected = :records_rejected,
                error_message = NULL
            WHERE ingestion_batch_id = :ingestion_batch_id;
            """
        ),
        {
            "ingestion_batch_id": ingestion_batch_id,
            "records_received": records_received,
            "records_loaded": records_loaded,
            "records_rejected": records_rejected,
        },
    )


def mark_batch_failed(
    session: Session,
    *,
    ingestion_batch_id: UUID,
    error_message: str,
    records_received: int | None = None,
    records_loaded: int | None = None,
    records_rejected: int | None = None,
) -> None:
    """
    Mark an ingestion batch as failed.

    Args:
        session: Active SQLAlchemy database session.
        ingestion_batch_id: ID of the ingestion batch.
        error_message: Description of the failure.
        records_received: Number of records received before failure.
        records_loaded: Number of records loaded before failure.
        records_rejected: Number of records rejected before failure.
    """
    session.execute(
        text(
            """
            UPDATE raw.ingestion_batches
            SET
                status = 'failed',
                completed_at = NOW(),
                records_received = :records_received,
                records_loaded = :records_loaded,
                records_rejected = :records_rejected,
                error_message = :error_message
            WHERE ingestion_batch_id = :ingestion_batch_id;
            """
        ),
        {
            "ingestion_batch_id": ingestion_batch_id,
            "records_received": records_received,
            "records_loaded": records_loaded,
            "records_rejected": records_rejected,
            "error_message": error_message,
        },
    )