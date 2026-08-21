"""
Extraction logic for product records.

Reads product records from raw.products for processing by the Product ETL
pipeline.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from etl.extract.base import BaseExtractor


class ProductExtractor(BaseExtractor):
    """
    Extract product records from raw.products.

    If an ingestion batch ID is provided, only records belonging to that
    batch are extracted. Otherwise, all raw product records are returned.
    """

    EXTRACT_SQL = text(
        """
        SELECT
            raw_id,
            ingestion_batch_id,
            source_row_number,
            source_row_hash,
            ingested_at,
            product_id,
            product_name,
            category,
            unit,
            selling_price,
            cost_price,
            opening_stock,
            reorder_level,
            active
        FROM raw.products
        WHERE (
            :batch_id IS NULL
            OR ingestion_batch_id = CAST(:batch_id AS uuid)
        )
        ORDER BY source_row_number;
        """
    )

    def extract(
        self,
        session: Session,
        batch_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Extract product records from the raw layer.

        Args:
            session: Active SQLAlchemy database session.
            batch_id: Optional raw ingestion batch ID. When provided, only
                records from that ingestion batch are extracted.

        Returns:
            A list of dictionaries representing raw product records.
        """
        result = session.execute(
            self.EXTRACT_SQL,
            {
                "batch_id": batch_id,
            },
        )

        return [
            dict(row)
            for row in result.mappings().all()
        ]