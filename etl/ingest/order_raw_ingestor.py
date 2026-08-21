"""
Raw ingestion logic for HBMS order data.

Reads Orders.csv and stores the source data in raw.orders without applying
business transformations. The raw layer preserves source values primarily
as text for traceability and reprocessing.
"""

from __future__ import annotations

import csv
import hashlib
import logging
from dataclasses import dataclass
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


@dataclass
class OrderRawIngestionResult:
    """Summary of an order raw ingestion run."""

    ingestion_batch_id: str
    records_received: int
    records_loaded: int
    records_rejected: int


class OrderRawIngestor:
    """
    Ingest Orders.csv into raw.orders.

    Source data is preserved with minimal processing. CSV column names are
    mapped to raw.orders columns, while fields unavailable in the source
    are stored as NULL.
    """

    SOURCE_SYSTEM = "HBMS"
    SOURCE_TYPE = "csv"
    SOURCE_TABLE = "orders"

    INSERT_SQL = text(
        """
        INSERT INTO raw.orders (
            ingestion_batch_id,
            source_row_number,
            source_row_hash,
            order_id,
            order_date,
            customer_id,
            subtotal,
            discount,
            delivery_charge,
            total_amount,
            paid,
            due,
            payment_method,
            order_status,
            notes,
            created_at,
            collected_by
        )
        VALUES (
            :ingestion_batch_id,
            :source_row_number,
            :source_row_hash,
            :order_id,
            :order_date,
            :customer_id,
            :subtotal,
            :discount,
            :delivery_charge,
            :total_amount,
            :paid,
            :due,
            :payment_method,
            :order_status,
            :notes,
            :created_at,
            :collected_by
        )
        ON CONFLICT (source_row_hash)
        DO NOTHING
        RETURNING raw_id;
        """
    )

    def __init__(self, csv_path: str | Path) -> None:
        self.csv_path = Path(csv_path)

    @staticmethod
    def _clean_value(value: Any) -> str | None:
        """Convert empty CSV values to None."""
        if value is None:
            return None

        value = str(value).strip()

        return value or None

    @staticmethod
    def _calculate_row_hash(row: dict[str, Any]) -> str:
        """
        Generate a deterministic hash for a source row.

        Sorting keys ensures the same logical row produces the same hash.
        """
        normalized = "|".join(
            f"{key}={row.get(key, '')}"
            for key in sorted(row.keys())
        )

        return hashlib.sha256(
            normalized.encode("utf-8")
        ).hexdigest()

    def ingest(self, session: Session) -> OrderRawIngestionResult:
        """
        Read Orders.csv and load records into raw.orders.
        """
        if not self.csv_path.exists():
            raise FileNotFoundError(
                f"Orders CSV file not found: {self.csv_path}"
            )

        batch_id = create_ingestion_batch(
            session,
            source_system=self.SOURCE_SYSTEM,
            source_type=self.SOURCE_TYPE,
            source_reference=str(self.csv_path),
        )

        records_received = 0
        records_loaded = 0
        records_rejected = 0

        logger.info(
            "Started order raw ingestion. Batch ID: %s",
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
                        payload = {
                            "ingestion_batch_id": batch_id,
                            "source_row_number": row_number,
                            "source_row_hash": self._calculate_row_hash(row),
                            "order_id": self._clean_value(
                                row.get("Order_ID")
                            ),
                            "order_date": self._clean_value(
                                row.get("Order_Date")
                            ),
                            "customer_id": self._clean_value(
                                row.get("Customer_ID")
                            ),
                            "subtotal": self._clean_value(
                                row.get("Subtotal")
                            ),
                            "discount": self._clean_value(
                                row.get("Discount")
                            ),
                            "delivery_charge": self._clean_value(
                                row.get("Delivery_Charge")
                            ),
                            "total_amount": self._clean_value(
                                row.get("Total_Amount")
                            ),
                            "paid": self._clean_value(
                                row.get("Paid")
                            ),
                            "due": self._clean_value(
                                row.get("Due")
                            ),
                            # Not currently available in Orders.csv.
                            "payment_method": None,
                            "order_status": self._clean_value(
                                row.get("Order_Status")
                            ),
                            # Not currently available in Orders.csv.
                            "notes": None,
                            "created_at": self._clean_value(
                                row.get("Created_At")
                            ),
                            "collected_by": self._clean_value(
                                row.get("Collected_By")
                            ),
                        }

                        result = session.execute(
                            self.INSERT_SQL,
                            payload,
                        )

                        if result.scalar_one_or_none() is not None:
                            records_loaded += 1

                    except Exception:
                        records_rejected += 1

                        logger.exception(
                            "Failed to ingest order row %s.",
                            row_number,
                        )

            mark_batch_completed(
                session,
                ingestion_batch_id=batch_id,
                records_received=records_received,
                records_loaded=records_loaded,
                records_rejected=records_rejected,
            )

            logger.info(
                "Order raw ingestion completed. "
                "Batch ID: %s, Received: %s, Loaded: %s, Rejected: %s",
                batch_id,
                records_received,
                records_loaded,
                records_rejected,
            )

            return OrderRawIngestionResult(
                ingestion_batch_id=str(batch_id),
                records_received=records_received,
                records_loaded=records_loaded,
                records_rejected=records_rejected,
            )

        except Exception as exc:
            logger.exception(
                "Order raw ingestion failed. Batch ID: %s",
                batch_id,
            )

            mark_batch_failed(
                session,
                ingestion_batch_id=batch_id,
                error_message=str(exc),
                records_received=records_received,
                records_loaded=records_loaded,
                records_rejected=records_rejected,
            )

            raise