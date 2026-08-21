"""
Extraction logic for return item records.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from etl.extract.base import BaseExtractor


class ReturnItemExtractor(BaseExtractor):
    """
    Extract return item records from raw.return_items.
    """

    EXTRACT_SQL = text(
        """
        SELECT
            raw_id,
            ingestion_batch_id,
            source_row_number,
            source_row_hash,
            return_item_id,
            return_id,
            product_id,
            quantity,
            unit_price,
            line_amount
        FROM raw.return_items
        ORDER BY ingested_at, source_row_number
        """
    )

    def extract(
        self,
        session: Session,
        batch_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Extract return item records.

        If batch_id is provided, extract only records from that
        raw ingestion batch.
        """

        if batch_id is not None:
            query = text(
                """
                SELECT
                    raw_id,
                    ingestion_batch_id,
                    source_row_number,
                    source_row_hash,
                    return_item_id,
                    return_id,
                    product_id,
                    quantity,
                    unit_price,
                    line_amount
                FROM raw.return_items
                WHERE ingestion_batch_id = :batch_id
                ORDER BY source_row_number
                """
            )

            result = session.execute(
                query,
                {
                    "batch_id": batch_id,
                },
            )
        else:
            result = session.execute(
                self.EXTRACT_SQL
            )

        return [
            dict(row._mapping)
            for row in result
        ]