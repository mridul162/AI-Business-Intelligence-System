"""
Loader for the core.dim_cash_account warehouse dimension.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session


class CashAccountDimensionLoader:
    """
    Load cash account master data from staging.stg_cash_accounts
    into core.dim_cash_account.
    """

    UPSERT_SQL = text(
        """
        INSERT INTO core.dim_cash_account (
            cash_account_id,
            account_name,
            account_type,
            owner_id,
            active
        )
        SELECT
            cash_account_id,
            account_name,
            account_type,
            owner_id,
            active
        FROM staging.stg_cash_accounts
        WHERE record_status = 'pending'
        ON CONFLICT (cash_account_id)
        DO UPDATE SET
            account_name = EXCLUDED.account_name,
            account_type = EXCLUDED.account_type,
            owner_id = EXCLUDED.owner_id,
            active = EXCLUDED.active;
        """
    )

    def __init__(
        self,
        session: Session,
    ) -> None:
        self.session = session

    def load(self) -> int:
        """
        Load cash account records from staging into the core dimension.

        New cash accounts are inserted. Existing cash accounts are
        updated using cash_account_id as the business key.

        Note:
            total_in, total_out, and current_balance are staging-only
            balance fields and are not carried into the dimension;
            they are expected to be derived from fact tables instead.

        Returns:
            Number of rows inserted or updated.
        """

        result = self.session.execute(
            self.UPSERT_SQL
        )

        return int(getattr(result, "rowcount", 0) or 0)