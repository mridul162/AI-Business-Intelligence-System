"""
Extraction logic for stock location records.

Extracts stock location records from raw.stock_locations.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from etl.extract.base import BaseExtractor


class StockLocationExtractor(BaseExtractor):
    """Extract stock location records from raw.stock_locations."""

    def extract(
        self,
        session: Session,
        batch_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Extract stock location records for a specific ingestion batch."""

        query = """
            SELECT
                raw_id,
                ingestion_batch_id,
                source_row_number,
                source_row_hash,
                stock_location_id,
                location_name,
                location_type,
                partner_id,
                active
            FROM raw.stock_locations
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