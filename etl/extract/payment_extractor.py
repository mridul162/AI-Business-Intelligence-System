"""
Extraction logic for payment records.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from etl.extract.base import BaseExtractor


class PaymentExtractor(BaseExtractor):
    """
    Extract payment records from raw.payments.
    """

    EXTRACT_SQL = text(
        """
        SELECT
            raw_id,
            ingestion_batch_id,
            source_row_hash,
            payment_id,
            payment_date,
            order_id,
            customer_id,
            amount,
            payment_method,
            cash_account_id,
            collected_by,
            notes,
            created_at
        FROM raw.payments
        WHERE NOT EXISTS (
            SELECT 1
            FROM staging.stg_payments
            WHERE staging.stg_payments.source_row_identifier =
                raw.payments.raw_id::text
        )
        ORDER BY ingested_at, raw_id;
        """
    )

    def extract(
        self,
        session: Session,
        batch_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Extract unprocessed payment records.

        If batch_id is provided, only extract records from that
        raw ingestion batch.
        """

        if batch_id is not None:
            sql = text(
                """
                SELECT
                    raw_id,
                    ingestion_batch_id,
                    source_row_hash,
                    payment_id,
                    payment_date,
                    order_id,
                    customer_id,
                    amount,
                    payment_method,
                    cash_account_id,
                    collected_by,
                    notes,
                    created_at
                FROM raw.payments
                WHERE ingestion_batch_id = :batch_id
                  AND NOT EXISTS (
                      SELECT 1
                      FROM staging.stg_payments
                      WHERE staging.stg_payments.source_row_identifier =
                          raw.payments.raw_id::text
                  )
                ORDER BY ingested_at, raw_id;
                """
            )

            result = session.execute(
                sql,
                {"batch_id": batch_id},
            )
        else:
            result = session.execute(
                self.EXTRACT_SQL
            )

        return [
            dict(row._mapping)
            for row in result
        ]