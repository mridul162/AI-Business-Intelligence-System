"""
Extraction logic for order records.

Extracts raw order records from raw.orders.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from etl.extract.base import BaseExtractor


class OrderExtractor(BaseExtractor):
    """Extract order records from the raw layer."""

    SELECT_SQL = text(
        """
        SELECT
            raw_id,
            ingestion_batch_id,
            source_row_number,
            source_row_hash,
            ingested_at,
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
        FROM raw.orders
        WHERE (
            :batch_id IS NULL
            OR ingestion_batch_id = :batch_id
        )
        ORDER BY source_row_number;
        """
    )

    def extract(
        self,
        session: Session,
        batch_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Extract order records from raw.orders."""
        result = session.execute(
            self.SELECT_SQL,
            {"batch_id": batch_id},
        )

        return [
            dict(row)
            for row in result.mappings().all()
        ]