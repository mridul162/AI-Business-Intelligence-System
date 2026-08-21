"""
Extraction logic for partner capital records.

Extracts partner capital records from raw.partner_capital.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from etl.extract.base import BaseExtractor


class PartnerCapitalExtractor(BaseExtractor):
    """Extract partner capital records from raw.partner_capital."""

    def extract(
        self,
        session: Session,
        batch_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Extract partner capital records for a specific ingestion batch."""

        query = """
            SELECT
                raw_id,
                ingestion_batch_id,
                source_row_number,
                source_row_hash,
                capital_transaction_id,
                transaction_date,
                partner_id,
                cash_account_id,
                transaction_type,
                amount,
                reference_id,
                notes,
                created_by,
                cash_transaction_id,
                created_at
            FROM raw.partner_capital
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