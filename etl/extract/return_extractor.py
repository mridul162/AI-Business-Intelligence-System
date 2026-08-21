"""
Extraction logic for return records.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from etl.extract.base import BaseExtractor


class ReturnExtractor(BaseExtractor):
    """Extract return records from raw.returns."""

    def extract(
        self,
        session: Session,
        batch_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Extract return records.

        If batch_id is provided, extract only records belonging to
        that ingestion batch.
        """

        query = """
            SELECT
                raw_id,
                ingestion_batch_id,
                source_row_number,
                source_row_hash,
                return_id,
                return_date,
                return_type,
                reference_order_id,
                reference_purchase_id,
                location_id,
                refund_amount,
                cash_account_id,
                returned_by,
                reason,
                status,
                notes,
                created_at
            FROM raw.returns
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