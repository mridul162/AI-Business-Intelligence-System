"""
Raw ingestion logic for return records.

Reads Returns.csv and loads source records into raw.returns.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
import hashlib
import logging
from pathlib import Path
from typing import Any

from sqlalchemy import text

from database.connection import session_scope

from etl.utils.ingestion_batch import (
    create_ingestion_batch,
    mark_batch_completed,
    mark_batch_failed,
)


logger = logging.getLogger(__name__)

@dataclass
class ReturnRawIngestionResult:
    """Summary of a return raw ingestion run."""

    ingestion_batch_id: str
    records_received: int
    records_loaded: int
    records_rejected: int

class ReturnRawIngestor:
    """Ingest Returns.csv records into raw.returns."""

    SOURCE_SYSTEM = "HBMS"
    SOURCE_TYPE = "csv"

    def __init__(
        self,
        file_path: str | Path,
    ) -> None:
        self.file_path = Path(file_path)

    @staticmethod
    def _generate_row_hash(
        row: dict[str, Any],
    ) -> str:
        """Generate a deterministic hash for a source row."""

        normalized_row = "|".join(
            f"{key}={row.get(key, '')}"
            for key in sorted(row.keys())
        )

        return hashlib.sha256(
            normalized_row.encode("utf-8")
        ).hexdigest()

    def ingest(self) -> ReturnRawIngestionResult:
        """Read the CSV file and ingest new records into raw.returns."""

        batch_id = None
        records_received = 0
        records_loaded = 0
        records_rejected = 0

        try:
            with session_scope() as session:
                batch_id = create_ingestion_batch(
                    session,
                    source_system=self.SOURCE_SYSTEM,
                    source_type=self.SOURCE_TYPE,
                    source_reference=str(
                        self.file_path.resolve()
                    ),
                )

            logger.info(
                "Started return raw ingestion. Batch ID: %s",
                batch_id,
            )

            with self.file_path.open(
                mode="r",
                encoding="utf-8-sig",
                newline="",
            ) as file:
                reader = csv.DictReader(file)

                for row_number, row in enumerate(
                    reader,
                    start=2,
                ):
                    records_received += 1

                    try:
                        source_row_hash = self._generate_row_hash(row)

                        with session_scope() as session:
                            exists = session.execute(
                                text(
                                    """
                                    SELECT EXISTS (
                                        SELECT 1
                                        FROM raw.returns
                                        WHERE source_row_hash =
                                            :source_row_hash
                                    );
                                    """
                                ),
                                {
                                    "source_row_hash": source_row_hash,
                                },
                            ).scalar()

                            if exists:
                                logger.debug(
                                    "Skipping duplicate return row %s.",
                                    row_number,
                                )
                                continue

                            session.execute(
                                text(
                                    """
                                    INSERT INTO raw.returns (
                                        ingestion_batch_id,
                                        source_row_number,
                                        source_row_hash,
                                        return_id,
                                        return_date,
                                        return_type,
                                        reference_order_id,
                                        reference_purchase_id,
                                        location_id,
                                        refund_amount,
                                        cash_account_id,
                                        returned_by,
                                        reason,
                                        status,
                                        notes,
                                        created_at
                                    )
                                    VALUES (
                                        :ingestion_batch_id,
                                        :source_row_number,
                                        :source_row_hash,
                                        :return_id,
                                        :return_date,
                                        :return_type,
                                        :reference_order_id,
                                        :reference_purchase_id,
                                        :location_id,
                                        :refund_amount,
                                        :cash_account_id,
                                        :returned_by,
                                        :reason,
                                        :status,
                                        :notes,
                                        :created_at
                                    );
                                    """
                                ),
                                {
                                    "ingestion_batch_id": batch_id,
                                    "source_row_number": row_number,
                                    "source_row_hash": source_row_hash,
                                    "return_id": row.get("Return_ID"),
                                    "return_date": row.get("Return_Date"),
                                    "return_type": row.get("Return_Type"),
                                    "reference_order_id": row.get(
                                        "Reference_Order_ID"
                                    ),
                                    "reference_purchase_id": row.get(
                                        "Reference_Purchase_ID"
                                    ),
                                    "location_id": row.get(
                                        "Location_ID"
                                    ),
                                    "refund_amount": row.get(
                                        "Refund_Amount"
                                    ),
                                    "cash_account_id": row.get(
                                        "Cash_Account_ID"
                                    ),
                                    "returned_by": row.get(
                                        "Returned_By"
                                    ),
                                    "reason": row.get("Reason"),
                                    "status": row.get("Status"),
                                    "notes": row.get("Notes"),
                                    "created_at": row.get("Created_At"),
                                },
                            )

                            records_loaded += 1

                    except Exception:
                        records_rejected += 1

                        logger.exception(
                            "Failed to ingest return row %s.",
                            row_number,
                        )

            with session_scope() as session:
                mark_batch_completed(
                    session,
                    ingestion_batch_id=batch_id,
                    records_received=records_received,
                    records_loaded=records_loaded,
                    records_rejected=records_rejected,
                )

            logger.info(
                "Return raw ingestion completed. "
                "Batch ID: %s, Received: %s, "
                "Loaded: %s, Rejected: %s",
                batch_id,
                records_received,
                records_loaded,
                records_rejected,
            )

            return ReturnRawIngestionResult(
                ingestion_batch_id=str(batch_id),
                records_received=records_received,
                records_loaded=records_loaded,
                records_rejected=records_rejected,
            )

        except Exception as exc:
            logger.exception(
                "Return raw ingestion failed. Batch ID: %s",
                batch_id,
            )

            if batch_id is not None:
                with session_scope() as session:
                    mark_batch_failed(
                        session,
                        ingestion_batch_id=batch_id,
                        error_message=str(exc),
                        records_received=records_received,
                        records_loaded=records_loaded,
                        records_rejected=records_rejected,
                    )

            raise