"""
Loading logic for cash transaction records.

Loads validated cash transaction records into
staging.stg_cash_transactions.

Note: raw.cash_transactions uses `cash_transaction_id` and
`created_at`, while staging.stg_cash_transactions names the
equivalent columns `transaction_id` and `source_created_at`.
CashTransactionTransformer renames these fields during
transformation. Also note that staging carries two columns —
`related_partner_id` and `notes` — that have no corresponding
source in raw.cash_transactions or the source CSV; the transformer
sets these to None and they are expected to be populated by
downstream enrichment, not by this pipeline.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from etl.load.base import BaseLoader


class CashTransactionLoader(BaseLoader):
    """Load cash transaction records into the staging layer."""

    INSERT_SQL = text(
        """
        INSERT INTO staging.stg_cash_transactions (
            transaction_id,
            transaction_date,
            cash_account_id,
            transaction_type,
            amount,
            related_partner_id,
            reference_id,
            notes,
            direction,
            reference_type,
            description,
            created_by,
            source_created_at,
            source_system,
            source_table,
            source_row_identifier,
            ingestion_batch_id,
            source_hash,
            record_status,
            validation_error
        )
        VALUES (
            :transaction_id,
            :transaction_date,
            :cash_account_id,
            :transaction_type,
            :amount,
            :related_partner_id,
            :reference_id,
            :notes,
            :direction,
            :reference_type,
            :description,
            :created_by,
            :source_created_at,
            :source_system,
            :source_table,
            :source_row_identifier,
            :ingestion_batch_id,
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
        """Load one cash transaction record."""

        self.session.execute(
            self.INSERT_SQL,
            data,
        )

    def load_many(
        self,
        records: list[dict[str, Any]],
    ) -> None:
        """Load multiple cash transaction records."""

        if not records:
            return

        self.session.execute(
            self.INSERT_SQL,
            records,
        )