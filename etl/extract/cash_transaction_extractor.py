"""
Extraction logic for cash transaction records.

Extracts cash transaction records from raw.cash_transactions.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from etl.extract.base import BaseExtractor


class CashTransactionExtractor(BaseExtractor):
    """Extract cash transaction records from raw.cash_transactions."""

    def extract(
        self,
        session: Session,
        batch_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Extract cash transaction records for a specific ingestion batch."""

        query = """
            SELECT
                raw_id,
                ingestion_batch_id,
                source_row_number,
                source_row_hash,
                cash_transaction_id,
                transaction_date,
                cash_account_id,
                transaction_type,
                direction,
                amount,
                reference_type,
                reference_id,
                description,
                created_at,
                created_by
            FROM raw.cash_transactions
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