"""
Raw ingestion logic for stock movement data.

Reads Stock_Movement.csv and ingests new records into
raw.stock_movements. Duplicate source records are skipped using
source_row_hash.
"""

from __future__ import annotations

import csv
import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from etl.utils.ingestion_batch import (
    create_ingestion_batch,
    mark_batch_completed,
    mark_batch_failed,
)


logger = logging.getLogger(__name__)


class StockMovementRawIngestor:
    """Ingest stock movement CSV records into raw.stock_movements."""

    SOURCE_SYSTEM = "HBMS"
    SOURCE_TYPE = "csv"

    INSERT_SQL = text(
        """
        INSERT INTO raw.stock_movements (
            ingestion_batch_id,
            source_row_number,
            source_row_hash,
            movement_id,
            movement_date,
            product_id,
            movement_type,
            reference_id,
            quantity,
            direction,
            from_location_id,
            to_location_id,
            notes,
            created_at
        )
        VALUES (
            :ingestion_batch_id,
            :source_row_number,
            :source_row_hash,
            :movement_id,
            :movement_date,
            :product_id,
            :movement_type,
            :reference_id,
            :quantity,
            :direction,
            :from_location_id,
            :to_location_id,
            :notes,
            :created_at
        );
        """
    )

    HASH_EXISTS_SQL = text(
        """
        SELECT EXISTS (
            SELECT 1
            FROM raw.stock_movements
            WHERE source_row_hash = :source_row_hash
        );
        """
    )

    def __init__(
        self,
        session: Session,
        csv_path: str | Path,
    ) -> None:
        self.session = session
        self.csv_path = Path(csv_path)

    @staticmethod
    def _clean_value(
        value: str | None,
    ) -> str | None:
        """Normalize CSV values."""

        if value is None:
            return None

        value = value.strip()

        return value or None

    @staticmethod
    def _generate_row_hash(
        record: dict[str, Any],
    ) -> str:
        """Generate a deterministic hash for a stock movement record."""

        normalized = json.dumps(
            record,
            sort_keys=True,
            default=str,
        )

        return hashlib.sha256(
            normalized.encode("utf-8")
        ).hexdigest()

    def _record_exists(
        self,
        source_row_hash: str,
    ) -> bool:
        """Check whether an identical source record already exists."""

        result = self.session.execute(
            self.HASH_EXISTS_SQL,
            {
                "source_row_hash": source_row_hash,
            },
        )

        return bool(result.scalar())

    def ingest(
        self,
    ) -> dict[str, Any]:
        """
        Read the CSV and ingest previously unseen stock movement
        records.
        """

        if not self.csv_path.exists():
            raise FileNotFoundError(
                f"CSV file not found: {self.csv_path}"
            )

        batch_id = create_ingestion_batch(
            self.session,
            source_system=self.SOURCE_SYSTEM,
            source_type=self.SOURCE_TYPE,
            source_reference=str(self.csv_path),
        )

        records_received = 0
        records_loaded = 0
        records_rejected = 0

        logger.info(
            "Started stock movement raw ingestion. Batch ID: %s",
            batch_id,
        )

        try:
            with self.csv_path.open(
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
                        stock_movement_record = {
                            "movement_id": self._clean_value(
                                row.get("Movement_ID")
                            ),
                            "movement_date": self._clean_value(
                                row.get("Movement_Date")
                            ),
                            "product_id": self._clean_value(
                                row.get("Product_ID")
                            ),
                            "movement_type": self._clean_value(
                                row.get("Movement_Type")
                            ),
                            "reference_id": self._clean_value(
                                row.get("Reference_ID")
                            ),
                            "quantity": self._clean_value(
                                row.get("Quantity")
                            ),
                            "direction": self._clean_value(
                                row.get("Direction")
                            ),
                            "from_location_id": self._clean_value(
                                row.get("From_Location_ID")
                            ),
                            "to_location_id": self._clean_value(
                                row.get("To_Location_ID")
                            ),
                            "notes": self._clean_value(
                                row.get("Notes")
                            ),
                            "created_at": self._clean_value(
                                row.get("Created_At")
                            ),
                        }

                        source_row_hash = (
                            self._generate_row_hash(
                                stock_movement_record
                            )
                        )

                        if self._record_exists(
                            source_row_hash
                        ):
                            continue

                        payload = {
                            "ingestion_batch_id": batch_id,
                            "source_row_number": row_number,
                            "source_row_hash": source_row_hash,
                            **stock_movement_record,
                        }

                        self.session.execute(
                            self.INSERT_SQL,
                            payload,
                        )

                        records_loaded += 1

                    except Exception:
                        records_rejected += 1

                        logger.exception(
                            "Failed to ingest stock movement row %s.",
                            row_number,
                        )

            mark_batch_completed(
                self.session,
                ingestion_batch_id=batch_id,
                records_received=records_received,
                records_loaded=records_loaded,
                records_rejected=records_rejected,
            )

            logger.info(
                "Stock movement raw ingestion completed. "
                "Batch ID: %s, Received: %s, Loaded: %s, "
                "Rejected: %s",
                batch_id,
                records_received,
                records_loaded,
                records_rejected,
            )

            return {
                "ingestion_batch_id": batch_id,
                "records_received": records_received,
                "records_loaded": records_loaded,
                "records_rejected": records_rejected,
            }

        except Exception as exc:
            logger.exception(
                "Stock movement raw ingestion failed. "
                "Batch ID: %s",
                batch_id,
            )

            mark_batch_failed(
                self.session,
                ingestion_batch_id=batch_id,
                error_message=str(exc),
                records_received=records_received,
                records_loaded=records_loaded,
                records_rejected=records_rejected,
            )

            raise