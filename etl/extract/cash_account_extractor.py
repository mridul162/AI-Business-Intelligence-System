"""
Extraction logic for cash account records.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from etl.extract.base import BaseExtractor


class CashAccountExtractor(BaseExtractor):
    """Extract cash account records from raw.cash_accounts."""

    SOURCE_TABLE = "cash_accounts"

    EXTRACT_SQL = text(
        """
        SELECT
            raw_id,
            ingestion_batch_id,
            cash_account_id,
            account_name,
            account_type,
            owner_id,
            active,
            total_in,
            total_out,
            current_balance,
            source_row_hash,
            ingested_at
        FROM raw.cash_accounts
        WHERE ingestion_batch_id = :batch_id
        ORDER BY source_row_number;
        """
    )

    def extract(
        self,
        session: Session,
        batch_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Extract records belonging to one ingestion batch."""

        if batch_id is None:
            raise ValueError(
                "batch_id is required for cash account extraction."
            )

        result = session.execute(
            self.EXTRACT_SQL,
            {"batch_id": batch_id},
        )

        return [
            dict(row)
            for row in result.mappings().all()
        ]