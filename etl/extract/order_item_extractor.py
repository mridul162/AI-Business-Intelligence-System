"""
Extraction logic for order item records.

Extracts raw order item records from raw.order_items.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from etl.extract.base import BaseExtractor


class OrderItemExtractor(BaseExtractor):
    """Extract order item records from raw.order_items."""

    EXTRACT_SQL = text(
        """
        SELECT
            raw_id,
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
        FROM raw.order_items
        ORDER BY ingested_at, source_row_number;
        """
    )

    def extract(
        self,
        session: Session,
        batch_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Extract order item records.

        If batch_id is provided, only records from that raw ingestion
        batch are extracted.
        """

        if batch_id is not None:
            sql = text(
                """
                SELECT
                    raw_id,
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
                FROM raw.order_items
                WHERE ingestion_batch_id = :batch_id
                ORDER BY source_row_number;
                """
            )

            result = session.execute(
                sql,
                {"batch_id": batch_id},
            )
        else:
            result = session.execute(self.EXTRACT_SQL)

        return [
            dict(row)
            for row in result.mappings().all()
        ]