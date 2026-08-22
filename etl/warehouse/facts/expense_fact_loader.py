"""
Warehouse loader for the expenses fact table.

Loads validated expense records from staging.stg_expenses into
core.fact_expenses and resolves warehouse dimension keys.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session


class ExpenseFactLoader:
    """Load expenses from staging into core.fact_expenses."""

    LOAD_SQL = text(
        """
        INSERT INTO core.fact_expenses (
            expense_id,
            date_key,
            expense_category,
            description,
            amount,
            payment_method,
            cash_account_key,
            paid_by,
            reference,
            created_by,
            created_at,
            source_system,
            source_table,
            source_row_identifier,
            ingestion_batch_id,
            ingested_at
        )
        SELECT
            stg.expense_id,
            d.date_key,
            COALESCE(stg.expense_category, 'uncategorized'),
            stg.description,
            stg.amount,
            COALESCE(stg.payment_method, 'unknown'),
            ca.cash_account_key,
            stg.paid_by,
            stg.reference_id,
            stg.created_by,
            stg.source_created_at,
            stg.source_system,
            stg.source_table,
            stg.source_row_identifier,
            stg.ingestion_batch_id,
            stg.ingested_at
        FROM (
            SELECT DISTINCT ON (expense_id)
                *
            FROM staging.stg_expenses
            WHERE record_status = 'pending'
            ORDER BY
                expense_id,
                ingested_at DESC,
                stg_expense_id DESC
        ) AS stg
        INNER JOIN core.dim_date AS d
            ON d.date = stg.expense_date
        LEFT JOIN core.dim_cash_account AS ca
            ON ca.cash_account_id = stg.cash_account_id

        ON CONFLICT (expense_id)
        DO UPDATE SET
            date_key = EXCLUDED.date_key,
            expense_category = EXCLUDED.expense_category,
            description = EXCLUDED.description,
            amount = EXCLUDED.amount,
            payment_method = EXCLUDED.payment_method,
            cash_account_key = EXCLUDED.cash_account_key,
            paid_by = EXCLUDED.paid_by,
            reference = EXCLUDED.reference,
            created_by = EXCLUDED.created_by,
            created_at = EXCLUDED.created_at,
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
        Load pending staging expenses into the warehouse.

        Existing expenses are updated (matched on expense_id), making
        the load idempotent.

        Dimension resolution:
            - date_key is resolved from core.dim_date via
              expense_date (INNER JOIN; required, NOT NULL).
            - cash_account_key is resolved from core.dim_cash_account
              via cash_account_id (LEFT JOIN; nullable on the fact
              table, since not every expense is tied to a tracked
              cash account).

        Column mapping notes:
            - staging.reference_id maps to fact.reference (renamed,
              not dropped).
            - staging.source_created_at maps to fact.created_at.
              core.fact_expenses has no separate source_created_at
              column, so this is treated as the expense's original
              creation timestamp rather than an ingestion-pipeline
              timestamp.
            - staging.paid_by_partner_id has no corresponding column
              on core.fact_expenses and is therefore not loaded.
              Only the free-text staging.paid_by is carried through.
              If the paying partner needs to be tracked as a proper
              dimension reference, fact_expenses would need a
              paid_by_partner_key column resolved against
              core.dim_partner.
            - expense_category and payment_method are NOT NULL on
              the fact table but nullable in staging, so they default
              to 'uncategorized' and 'unknown' respectively when
              missing, mirroring the order_status/payment_method
              defaulting used in the other fact loaders.

        Returns:
            Number of rows inserted or updated.
        """

        result = self.session.execute(
            self.LOAD_SQL
        )

        return int(getattr(result, "rowcount", 0) or 0)