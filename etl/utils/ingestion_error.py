"""
Utilities for recording ETL ingestion and validation errors.

Errors are persisted in raw.ingestion_errors so rejected records
can be investigated after a pipeline run.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session


INSERT_INGESTION_ERROR_SQL = text(
    """
    INSERT INTO raw.ingestion_errors (
        ingestion_batch_id,
        source_table,
        source_row_identifier,
        error_type,
        error_message,
        raw_payload
    )
    VALUES (
        :ingestion_batch_id,
        :source_table,
        :source_row_identifier,
        :error_type,
        :error_message,
        CAST(:raw_payload AS jsonb)
    );
    """
)


def record_ingestion_error(
    session: Session,
    *,
    ingestion_batch_id: UUID | str,
    source_table: str,
    source_row_identifier: str | None,
    error_type: str,
    error_message: str,
    raw_payload: dict[str, Any] | None = None,
) -> None:
    """
    Persist an ingestion or validation error.

    Args:
        session: Active SQLAlchemy database session.
        ingestion_batch_id: Batch associated with the failed record.
        source_table: Source table where the record originated.
        source_row_identifier: Identifier of the source record.
        error_type: Classification of the error.
        error_message: Human-readable error details.
        raw_payload: Original or transformed record payload.
    """

    session.execute(
        INSERT_INGESTION_ERROR_SQL,
        {
            "ingestion_batch_id": str(ingestion_batch_id),
            "source_table": source_table,
            "source_row_identifier": source_row_identifier,
            "error_type": error_type,
            "error_message": error_message,
            "raw_payload": (
                json.dumps(
                    raw_payload,
                    default=str,
                )
                if raw_payload is not None
                else None
            ),
        },
    )