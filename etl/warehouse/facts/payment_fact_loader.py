"""
Warehouse loader for the payments fact table.

Loads validated payment records from staging.stg_payments into
core.fact_payments and resolves warehouse dimension keys.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session


class PaymentFactLoader:
    """Load payments from staging into core.fact_payments."""

    LOAD_SQL = text(
        """
        INSERT INTO core.fact_payments (
            payment_id,
            date_key,
            order_id,
            customer_key,
            cash_account_key,
            amount,
            payment_method,
            collected_by,
            notes,
            source_created_at,
            source_system,
            source_table,
            source_row_identifier,
            ingestion_batch_id,
            ingested_at
        )
        SELECT
            stg.payment_id,
            d.date_key,
            stg.order_id,
            c.customer_key,
            ca.cash_account_key,
            stg.amount,
            COALESCE(stg.payment_method, 'unknown'),
            stg.collected_by,
            stg.notes,
            stg.source_created_at,
            stg.source_system,
            stg.source_table,
            stg.source_row_identifier,
            stg.ingestion_batch_id,
            stg.ingested_at
        FROM (
            SELECT DISTINCT ON (payment_id)
                *
            FROM staging.stg_payments
            WHERE record_status = 'pending'
            ORDER BY
                payment_id,
                ingested_at DESC,
                stg_payment_id DESC
        ) AS stg
        INNER JOIN core.dim_date AS d
            ON d.date = stg.payment_date
        LEFT JOIN core.dim_customer AS c
            ON c.customer_id = stg.customer_id
            AND c.is_current = TRUE
        LEFT JOIN core.dim_cash_account AS ca
            ON ca.cash_account_id = stg.cash_account_id

        ON CONFLICT (payment_id)
        DO UPDATE SET
            date_key = EXCLUDED.date_key,
            order_id = EXCLUDED.order_id,
            customer_key = EXCLUDED.customer_key,
            cash_account_key = EXCLUDED.cash_account_key,
            amount = EXCLUDED.amount,
            payment_method = EXCLUDED.payment_method,
            collected_by = EXCLUDED.collected_by,
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
        """
        Load pending staging payments into the warehouse.

        Existing payments are updated (matched on payment_id), making
        the load idempotent.

        Dimension resolution:
            - date_key is resolved from core.dim_date via
              payment_date and is required (INNER JOIN), since
              date_key is NOT NULL on core.fact_payments. A payment
              whose date has no matching dim_date row is excluded
              from this load.
            - customer_key is resolved from core.dim_customer via
              customer_id, restricted to the current row
              (is_current = TRUE), and left nullable since not every
              payment is tied to a known customer.
            - cash_account_key is resolved from core.dim_cash_account
              via cash_account_id and left nullable for the same
              reason.

        Note:
            order_id is carried through as-is from staging even
            though it is NOT NULL on core.fact_payments while
            nullable on staging.stg_payments; a payment with a NULL
            order_id in staging will fail the insert rather than be
            silently dropped or coerced, since that mismatch usually
            indicates a staging/validation gap worth surfacing rather
            than papering over.

        Returns:
            Number of rows inserted or updated.
        """

        result = self.session.execute(
            self.LOAD_SQL
        )

        return int(getattr(result, "rowcount", 0) or 0)