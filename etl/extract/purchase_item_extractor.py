"""
Extraction logic for purchase item records.

Extracts purchase item records from raw.purchase_items.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from etl.extract.base import BaseExtractor


class PurchaseItemExtractor(BaseExtractor):
    """Extract purchase item records from raw.purchase_items."""

    def extract(
        self,
        session: Session,
        batch_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Extract purchase item records for a specific ingestion batch."""

        query = """
            SELECT
                raw_id,
                ingestion_batch_id,
                source_row_number,
                source_row_hash,
                purchase_item_id,
                purchase_id,
                product_id,
                quantity,
                unit_cost,
                discount,
                line_total,
                stock_location_id
            FROM raw.purchase_items
        """

        params: dict[str, Any] = {}

        if batch_id is not None:
            query += """
                WHERE ingestion_batch_id = :batch_id
            """

            params["batch_id"] = batch_id

        query += """
            ORDER BY source_row_number
        """

        result = session.execute(
            text(query),
            params,
        )

        return [
            dict(row)
            for row in result.mappings().all()
        ]