"""
Extraction logic for expense records.

Extracts expense records from raw.expenses.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from etl.extract.base import BaseExtractor


class ExpenseExtractor(BaseExtractor):
    """Extract expense records from raw.expenses."""

    def extract(
        self,
        session: Session,
        batch_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Extract expense records for a specific ingestion batch."""

        query = """
            SELECT
                raw_id,
                ingestion_batch_id,
                source_row_number,
                source_row_hash,
                expense_id,
                expense_date,
                expense_category,
                description,
                amount,
                payment_method,
                paid_by,
                partner_id,
                cash_account_id,
                reference_id,
                created_by,
                created_at
            FROM raw.expenses
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