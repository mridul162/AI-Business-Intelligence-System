"""
Raw ingestion logic for return item records.

Reads Return_Items.csv and loads source records into raw.return_items.
Each ingestion run is tracked through raw.ingestion_batches.
"""

from __future__ import annotations

import csv
import hashlib
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


class ReturnItemRawIngestor:
    """
    Ingest return item data from a CSV export into raw.return_items.
    """

    SOURCE_SYSTEM = "HBMS"
    SOURCE_TYPE = "csv"
    SOURCE_TABLE = "return_items"

    INSERT_SQL = text(
        """
        INSERT INTO raw.return_items (
            ingestion_batch_id,
            source_row_number,
            source_row_hash,
            return_item_id,
            return_id,
            product_id,
            quantity,
            unit_price,
            line_amount
        )
        VALUES (
            :ingestion_batch_id,
            :source_row_number,
            :source_row_hash,
            :return_item_id,
            :return_id,
            :product_id,
            :quantity,
            :unit_price,
            :line_amount
        )
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
    def _clean_value(value: Any) -> str | None:
        """Convert empty source values to None."""
        if value is None:
            return None

        value = str(value).strip()

        return value or None

    @staticmethod
    def _generate_row_hash(
        row: dict[str, Any],
    ) -> str:
        """Generate a deterministic hash for a source row."""

        normalized_values = [
            str(value).strip()
            for key, value in sorted(row.items())
        ]

        payload = "|".join(normalized_values)

        return hashlib.sha256(
            payload.encode("utf-8")
        ).hexdigest()

    def _record_exists(
        self,
        source_row_hash: str,
    ) -> bool:
        """Check whether an identical source record already exists."""

        result = self.session.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM raw.return_items
                    WHERE source_row_hash = :source_row_hash
                )
                """
            ),
            {
                "source_row_hash": source_row_hash,
            },
        )

        return bool(result.scalar())

    def ingest(self) -> dict[str, Any]:
        """
        Execute raw ingestion from CSV into raw.return_items.
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
            "Started return item raw ingestion. Batch ID: %s",
            batch_id,
        )

        try:
            with self.csv_path.open(
                mode="r",
                encoding="utf-8-sig",
                newline="",
            ) as csv_file:

                reader = csv.DictReader(csv_file)

                for row_number, row in enumerate(
                    reader,
                    start=2,
                ):
                    records_received += 1

                    try:
                        source_row_hash = self._generate_row_hash(
                            row
                        )

                        if self._record_exists(source_row_hash):
                            continue

                        payload = {
                            "ingestion_batch_id": batch_id,
                            "source_row_number": row_number,
                            "source_row_hash": source_row_hash,
                            "return_item_id": self._clean_value(
                                row.get("Return_Item_ID")
                            ),
                            "return_id": self._clean_value(
                                row.get("Return_ID")
                            ),
                            "product_id": self._clean_value(
                                row.get("Product_ID")
                            ),
                            "quantity": self._clean_value(
                                row.get("Quantity")
                            ),
                            "unit_price": self._clean_value(
                                row.get("Unit_Price")
                            ),
                            "line_amount": self._clean_value(
                                row.get("Line_Amount")
                            ),
                        }

                        self.session.execute(
                            self.INSERT_SQL,
                            payload,
                        )

                        records_loaded += 1

                    except Exception:
                        records_rejected += 1

                        logger.exception(
                            "Failed to ingest return item row %s.",
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
                "Return item raw ingestion completed. "
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
                "Return item raw ingestion failed. "
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