"""
Raw ingestion logic for order item data.

Reads Order_Items.csv and loads source records into raw.order_items.
The raw layer preserves source values as text and tracks each ingestion
run through raw.ingestion_batches.
"""

from __future__ import annotations

import csv
import hashlib
import json
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
class OrderItemRawIngestionResult:
    """Summary of an order item raw ingestion run."""

    ingestion_batch_id: str
    records_received: int
    records_loaded: int
    records_rejected: int


class OrderItemRawIngestor:
    """
    Ingest Order_Items.csv records into raw.order_items.

    Duplicate source rows are skipped based on source_row_hash.
    """

    SOURCE_SYSTEM = "HBMS"
    SOURCE_TYPE = "csv"
    SOURCE_TABLE = "order_items"

    INSERT_SQL = text(
        """
        INSERT INTO raw.order_items (
            ingestion_batch_id,
            source_row_number,
            source_row_hash,
            order_item_id,
            order_id,
            product_id,
            quantity,
            unit_price,
            discount,
            line_total,
            cost_price,
            cogs,
            fulfilled_from_location_id
        )
        SELECT
            :ingestion_batch_id,
            :source_row_number,
            :source_row_hash,
            :order_item_id,
            :order_id,
            :product_id,
            :quantity,
            :unit_price,
            :discount,
            :line_total,
            :cost_price,
            :cogs,
            :fulfilled_from_location_id
        WHERE NOT EXISTS (
            SELECT 1
            FROM raw.order_items
            WHERE source_row_hash = :source_row_hash
        );
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
    def _build_row_hash(row: dict[str, Any]) -> str:
        """Create a deterministic hash from the source row."""
        normalized = {
            key: "" if value is None else str(value).strip()
            for key, value in sorted(row.items())
        }

        payload = json.dumps(
            normalized,
            sort_keys=True,
            ensure_ascii=False,
        )

        return hashlib.sha256(
            payload.encode("utf-8")
        ).hexdigest()

    def _read_csv(self) -> list[dict[str, Any]]:
        """Read Order_Items.csv."""
        if not self.csv_path.exists():
            raise FileNotFoundError(
                f"Order items CSV file not found: {self.csv_path}"
            )

        with self.csv_path.open(
            mode="r",
            encoding="utf-8-sig",
            newline="",
        ) as file:
            reader = csv.DictReader(file)
            return list(reader)

    def ingest(
        self,
        session: Session,
    ) -> OrderItemRawIngestionResult:
        """Ingest CSV records into raw.order_items."""

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
            "Started order item raw ingestion. Batch ID: %s",
            batch_id,
        )

        try:
            rows = self._read_csv()
            records_received = len(rows)

            for row_number, row in enumerate(rows, start=2):
                try:
                    source_row_hash = self._build_row_hash(row)

                    payload = {
                        "ingestion_batch_id": batch_id,
                        "source_row_number": row_number,
                        "source_row_hash": source_row_hash,
                        "order_item_id": self._clean_value(
                            row.get("Order_Item_ID")
                        ),
                        "order_id": self._clean_value(
                            row.get("Order_ID")
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
                        "discount": self._clean_value(
                            row.get("Discount")
                        ),
                        "line_total": self._clean_value(
                            row.get("Line_Total")
                        ),
                        "cost_price": self._clean_value(
                            row.get("Cost_Price")
                        ),
                        "cogs": self._clean_value(
                            row.get("COGS")
                        ),
                        "fulfilled_from_location_id": self._clean_value(
                            row.get("Fulfilled_From_Location_ID")
                        ),
                    }

                    result = session.execute(
                        self.INSERT_SQL,
                        payload,
                    )

                    if result.rowcount > 0:
                        records_loaded += 1

                except Exception:
                    records_rejected += 1
                    logger.exception(
                        "Failed to ingest order item CSV row %s.",
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
                "Order item raw ingestion completed. "
                "Batch ID: %s, Received: %s, Loaded: %s, Rejected: %s",
                batch_id,
                records_received,
                records_loaded,
                records_rejected,
            )

            return OrderItemRawIngestionResult(
                ingestion_batch_id=str(batch_id),
                records_received=records_received,
                records_loaded=records_loaded,
                records_rejected=records_rejected,
            )

        except Exception as exc:
            logger.exception(
                "Order item raw ingestion failed. Batch ID: %s",
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