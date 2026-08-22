"""
Warehouse loader for the partner capital fact table.

Loads validated partner capital entries from
staging.stg_partner_capital into core.fact_partner_capital and
resolves warehouse dimension keys.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session


class PartnerCapitalFactLoader:
    """Load partner capital entries from staging into core.fact_partner_capital."""

    LOAD_SQL = text(
        """
        INSERT INTO core.fact_partner_capital (
            capital_transaction_id,
            date_key,
            partner_key,
            cash_account_key,
            transaction_type,
            amount,
            reference_id,
            notes,
            created_by,
            created_at,
            source_system,
            source_table,
            source_row_identifier,
            ingestion_batch_id,
            ingested_at
        )
        SELECT
            stg.capital_transaction_id,
            d.date_key,
            p.partner_key,
            ca.cash_account_key,
            stg.transaction_type,
            stg.amount,
            stg.reference_id,
            stg.notes,
            stg.created_by,
            stg.source_created_at,
            stg.source_system,
            stg.source_table,
            stg.source_row_identifier,
            stg.ingestion_batch_id,
            stg.ingested_at
        FROM (
            SELECT DISTINCT ON (partner_capital_entry_id)
                *
            FROM staging.stg_partner_capital
            WHERE record_status = 'pending'
            ORDER BY
                partner_capital_entry_id,
                ingested_at DESC,
                stg_partner_capital_id DESC
        ) AS stg
        INNER JOIN core.dim_date AS d
            ON d.date = stg.entry_date
        INNER JOIN core.dim_partner AS p
            ON p.partner_id = stg.partner_id
        INNER JOIN core.dim_cash_account AS ca
            ON ca.cash_account_id = stg.cash_account_id

        ON CONFLICT (capital_transaction_id)
        DO UPDATE SET
            date_key = EXCLUDED.date_key,
            partner_key = EXCLUDED.partner_key,
            cash_account_key = EXCLUDED.cash_account_key,
            transaction_type = EXCLUDED.transaction_type,
            amount = EXCLUDED.amount,
            reference_id = EXCLUDED.reference_id,
            notes = EXCLUDED.notes,
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
        Load pending staging partner capital entries into the
        warehouse.

        Existing entries are updated (matched on
        capital_transaction_id), making the load idempotent.

        Dimension resolution:
            - date_key is resolved from core.dim_date via entry_date
              (INNER JOIN; required, NOT NULL).
            - partner_key is resolved from core.dim_partner via
              partner_id (INNER JOIN; required, NOT NULL).
            - cash_account_key is resolved from core.dim_cash_account
              via cash_account_id (INNER JOIN; required, NOT NULL,
              even though cash_account_id is nullable in staging). A
              staging row with a missing or unresolvable
              cash_account_id is excluded from this load rather than
              failing it.

        Business key caution:
            staging.stg_partner_capital has two different candidate
            identifiers, and this loader uses them for two different
            purposes:
                - partner_capital_entry_id (NOT NULL) is used only to
                  deduplicate re-ingested staging rows before insert,
                  the same way every other loader dedupes on its
                  staging table's own row identifier.
                - capital_transaction_id (nullable) is loaded as the
                  fact table's actual business key and conflict
                  target, since core.fact_partner_capital's own
                  unique constraint and column are both named
                  capital_transaction_id.
            Because capital_transaction_id is nullable in staging but
            NOT NULL on the fact table, a pending row with a null
            capital_transaction_id will fail the insert rather than
            silently falling back to partner_capital_entry_id. Please
            confirm capital_transaction_id (not
            partner_capital_entry_id) is really meant to be the
            fact table's business key -- if partner_capital_entry_id
            is actually the intended identifier, the INSERT and
            ON CONFLICT clauses should be switched to use it instead.

        Column notes:
            - staging.source_created_at maps to fact.created_at,
              mirroring the same rename used in the expense loader.

        Returns:
            Number of rows inserted or updated.
        """

        result = self.session.execute(
            self.LOAD_SQL
        )

        return int(getattr(result, "rowcount", 0) or 0)