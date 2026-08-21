"""
Loading logic for staging cash account records.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from etl.load.base import BaseLoader


class CashAccountLoader(BaseLoader):
    """Load validated records into staging.stg_cash_accounts."""

    INSERT_SQL = text(
        """
        INSERT INTO staging.stg_cash_accounts (
            cash_account_id,
            account_name,
            account_type,
            owner_id,
            active,
            total_in,
            total_out,
            current_balance,
            source_system,
            source_table,
            source_row_identifier,
            ingestion_batch_id,
            ingested_at,
            source_hash,
            record_status,
            validation_error
        )
        VALUES (
            :cash_account_id,
            :account_name,
            :account_type,
            :owner_id,
            :active,
            :total_in,
            :total_out,
            :current_balance,
            :source_system,
            :source_table,
            :source_row_identifier,
            :ingestion_batch_id,
            :ingested_at,
            :source_hash,
            :record_status,
            :validation_error
        )
        ON CONFLICT (
            ingestion_batch_id,
            source_table,
            source_row_identifier
        )
        DO NOTHING;
        """
    )

    def __init__(
        self,
        session: Session,
    ) -> None:
        self.session = session

    def load(
        self,
        data: dict[str, Any],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Load one prepared return item record."""

        self.session.execute(
            self.INSERT_SQL,
            data,
        )

    def load_many(
        self,
        records: list[dict[str, Any]],
    ) -> int:
        """
        Load multiple prepared return item records.

        Returns the number of records submitted for loading.
        """

        if not records:
            return 0

        self.session.execute(
            self.INSERT_SQL,
            records,
        )

        return len(records)