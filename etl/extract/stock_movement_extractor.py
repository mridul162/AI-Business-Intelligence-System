"""
Extraction logic for stock movement records.

Extracts stock movement records from raw.stock_movements.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from etl.extract.base import BaseExtractor


class StockMovementExtractor(BaseExtractor):
    """Extract stock movement records from raw.stock_movements."""

    def extract(
        self,
        session: Session,
        batch_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Extract stock movement records for a specific ingestion batch."""

        query = """
            SELECT
                raw_id,
                ingestion_batch_id,
                source_row_number,
                source_row_hash,
                movement_id,
                movement_date,
                product_id,
                movement_type,
                direction,
                quantity,
                from_location_id,
                to_location_id,
                reference_id,
                notes,
                created_at
            FROM raw.stock_movements
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