"""
Warehouse loader for return facts.

Loads the latest valid version of each return from staging.stg_returns
into core.fact_returns.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session


class ReturnFactLoader:
    """Load return facts into core.fact_returns."""

    LOAD_SQL = text(
        """
        INSERT INTO core.fact_returns (
            return_id,
            date_key,
            return_type,
            order_id,
            purchase_id,
            customer_key,
            location_key,
            cash_account_key,
            refund_amount,
            due_adjustment,
            cash_refund,
            returned_by,
            reason,
            status,
            notes,
            source_created_at,
            source_system,
            source_table,
            source_row_identifier,
            ingestion_batch_id,
            ingested_at
        )
        SELECT
            stg.return_id,
            d.date_key,
            UPPER(stg.return_type),
            stg.order_id,
            stg.purchase_id,
            c.customer_key,
            l.location_key,
            ca.cash_account_key,
            COALESCE(stg.refund_amount, 0),
            COALESCE(stg.adjustment_amount, 0),
            GREATEST(
                COALESCE(stg.refund_amount, 0)
                - COALESCE(stg.adjustment_amount, 0),
                0
            ),
            stg.returned_by,
            stg.reason,
            COALESCE(stg.return_status, 'unknown'),
            stg.notes,
            stg.source_created_at,
            stg.source_system,
            stg.source_table,
            stg.source_row_identifier,
            stg.ingestion_batch_id,
            stg.ingested_at
        FROM (
            SELECT DISTINCT ON (return_id)
                *
            FROM staging.stg_returns
            WHERE record_status = 'pending'
            ORDER BY
                return_id,
                ingested_at DESC,
                stg_return_id DESC
        ) AS stg

        INNER JOIN core.dim_date AS d
            ON d.date = stg.return_date

        LEFT JOIN core.dim_customer AS c
            ON c.customer_id = stg.customer_id
            AND c.is_current = TRUE

        INNER JOIN core.dim_location AS l
            ON l.stock_location_id = stg.location_id
            AND l.active = TRUE

        INNER JOIN core.dim_cash_account AS ca
            ON ca.cash_account_id = stg.cash_account_id
            AND ca.active = TRUE

        ON CONFLICT (return_id)
        DO UPDATE SET
            date_key = EXCLUDED.date_key,
            return_type = EXCLUDED.return_type,
            order_id = EXCLUDED.order_id,
            purchase_id = EXCLUDED.purchase_id,
            customer_key = EXCLUDED.customer_key,
            location_key = EXCLUDED.location_key,
            cash_account_key = EXCLUDED.cash_account_key,
            refund_amount = EXCLUDED.refund_amount,
            due_adjustment = EXCLUDED.due_adjustment,
            cash_refund = EXCLUDED.cash_refund,
            returned_by = EXCLUDED.returned_by,
            reason = EXCLUDED.reason,
            status = EXCLUDED.status,
            notes = EXCLUDED.notes,
            source_created_at = EXCLUDED.source_created_at,
            source_system = EXCLUDED.source_system,
            source_table = EXCLUDED.source_table,
            source_row_identifier = EXCLUDED.source_row_identifier,
            ingestion_batch_id = EXCLUDED.ingestion_batch_id,
            ingested_at = EXCLUDED.ingested_at;
        """
    )

    def __init__(
        self,
        session: Session,
    ) -> None:
        self.session = session

    def load(self) -> int:
        """Load returns into the warehouse fact table."""

        result = self.session.execute(
            self.LOAD_SQL
        )

        return int(getattr(result, "rowcount", 0) or 0)