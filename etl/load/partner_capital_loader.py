"""
Loading logic for partner capital records.

Loads validated partner capital records into
staging.stg_partner_capital.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from etl.load.base import BaseLoader


class PartnerCapitalLoader(BaseLoader):
    """Load partner capital records into the staging layer."""

    INSERT_SQL = text(
        """
        INSERT INTO staging.stg_partner_capital (
            partner_capital_entry_id,
            entry_date,
            partner_id,
            transaction_type,
            amount,
            cash_account_id,
            notes,
            source_system,
            source_table,
            source_row_identifier,
            ingestion_batch_id,
            source_hash,
            record_status,
            validation_error,
            capital_transaction_id,
            reference_id,
            created_by,
            source_created_at
        )
        VALUES (
            :partner_capital_entry_id,
            :entry_date,
            :partner_id,
            :transaction_type,
            :amount,
            :cash_account_id,
            :notes,
            :source_system,
            :source_table,
            :source_row_identifier,
            :ingestion_batch_id,
            :source_hash,
            :record_status,
            :validation_error,
            :capital_transaction_id,
            :reference_id,
            :created_by,
            :source_created_at
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
        """Load one partner capital record."""

        self.session.execute(
            self.INSERT_SQL,
            data,
        )

    def load_many(
        self,
        records: list[dict[str, Any]],
    ) -> None:
        """Load multiple partner capital records."""

        if not records:
            return

        self.session.execute(
            self.INSERT_SQL,
            records,
        )