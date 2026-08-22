"""
Warehouse loader for the cash transactions fact table.

Loads validated cash transaction records from
staging.stg_cash_transactions into core.fact_cash_transactions and
resolves warehouse dimension keys.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session


class CashTransactionFactLoader:
    """Load cash transactions from staging into core.fact_cash_transactions."""

    LOAD_SQL = text(
        """
        INSERT INTO core.fact_cash_transactions (
            transaction_id,
            date_key,
            cash_account_key,
            transaction_type,
            direction,
            amount,
            reference_type,
            reference_id,
            description,
            created_by,
            source_created_at,
            source_system,
            source_table,
            source_row_identifier,
            ingestion_batch_id,
            ingested_at
        )
        SELECT
            stg.transaction_id,
            d.date_key,
            ca.cash_account_key,
            stg.transaction_type,
            stg.direction,
            stg.amount,
            stg.reference_type,
            stg.reference_id,
            COALESCE(stg.description, stg.notes),
            stg.created_by,
            stg.source_created_at,
            stg.source_system,
            stg.source_table,
            stg.source_row_identifier,
            stg.ingestion_batch_id,
            stg.ingested_at
        FROM (
            SELECT DISTINCT ON (transaction_id)
                *
            FROM staging.stg_cash_transactions
            WHERE record_status = 'pending'
            ORDER BY
                transaction_id,
                ingested_at DESC,
                stg_cash_transaction_id DESC
        ) AS stg
        INNER JOIN core.dim_date AS d
            ON d.date = stg.transaction_date
        INNER JOIN core.dim_cash_account AS ca
            ON ca.cash_account_id = stg.cash_account_id

        ON CONFLICT (transaction_id)
        DO UPDATE SET
            date_key = EXCLUDED.date_key,
            cash_account_key = EXCLUDED.cash_account_key,
            transaction_type = EXCLUDED.transaction_type,
            direction = EXCLUDED.direction,
            amount = EXCLUDED.amount,
            reference_type = EXCLUDED.reference_type,
            reference_id = EXCLUDED.reference_id,
            description = EXCLUDED.description,
            created_by = EXCLUDED.created_by,
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
        Load pending staging cash transactions into the warehouse.

        Existing transactions are updated (matched on
        transaction_id), making the load idempotent.

        Dimension resolution:
            - date_key is resolved from core.dim_date via
              transaction_date (INNER JOIN; required, NOT NULL).
            - cash_account_key is resolved from core.dim_cash_account
              via cash_account_id (INNER JOIN; required, NOT NULL).
              A transaction whose cash_account_id is missing or
              unresolvable is excluded from this load rather than
              failing it, since cash_account_id is nullable in
              staging but NOT NULL on the fact table.

        Column notes:
            - related_partner_id exists on staging.stg_cash_transactions
              but has no corresponding column on
              core.fact_cash_transactions, so it is not loaded. If
              tracking the counterparty on cash transactions is
              needed, that column will need to be added to the fact
              table (likely as a partner_key resolved against
              core.dim_partner).
            - staging carries both notes and description as separate
              free-text columns, while the fact table has only
              description. These are treated as redundant and merged
              with COALESCE(description, notes), preferring
              description when both are populated. Confirm this is
              the right precedence if the two columns are ever
              populated with different, non-overlapping information.
            - transaction_type and direction are passed through as-is
              from staging. direction is constrained on the fact
              table to only 'IN' or 'OUT'; a staging row with a null
              or different value will fail the insert rather than be
              coerced, since guessing a direction risks silently
              misclassifying money movement.

        Returns:
            Number of rows inserted or updated.
        """

        result = self.session.execute(
            self.LOAD_SQL
        )

        return int(getattr(result, "rowcount", 0) or 0)