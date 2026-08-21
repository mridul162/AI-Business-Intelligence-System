"""
Extraction logic for purchase records.

Extracts purchase records from raw.purchases.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from etl.extract.base import BaseExtractor


class PurchaseExtractor(BaseExtractor):
    """Extract purchase records from raw.purchases."""

    def extract(
        self,
        session: Session,
        batch_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Extract purchase records for a specific ingestion batch."""

        query = """
            SELECT
                raw_id,
                ingestion_batch_id,
                source_row_number,
                source_row_hash,
                purchase_id,
                purchase_date,
                supplier_id,
                subtotal,
                discount,
                other_charges,
                total_amount,
                paid,
                due,
                payment_method,
                cash_account_id,
                purchased_by,
                purchase_status,
                notes,
                created_at
            FROM raw.purchases
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