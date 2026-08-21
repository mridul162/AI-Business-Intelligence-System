"""
Loading logic for expense records.

Loads validated expense records into staging.stg_expenses.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from etl.load.base import BaseLoader


class ExpenseLoader(BaseLoader):
    """Load expense records into the staging layer."""

    INSERT_SQL = text(
        """
        INSERT INTO staging.stg_expenses (
            expense_id,
            expense_date,
            expense_category,
            description,
            amount,
            paid_by_partner_id,
            cash_account_id,
            reference_id,
            source_system,
            source_table,
            source_row_identifier,
            ingestion_batch_id,
            source_hash,
            record_status,
            validation_error,
            payment_method,
            paid_by,
            created_by,
            source_created_at
        )
        VALUES (
            :expense_id,
            :expense_date,
            :expense_category,
            :description,
            :amount,
            :paid_by_partner_id,
            :cash_account_id,
            :reference_id,
            :source_system,
            :source_table,
            :source_row_identifier,
            :ingestion_batch_id,
            :source_hash,
            :record_status,
            :validation_error,
            :payment_method,
            :paid_by,
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
        """Load one expense record."""

        self.session.execute(
            self.INSERT_SQL,
            data,
        )

    def load_many(
        self,
        records: list[dict[str, Any]],
    ) -> None:
        """Load multiple expense records."""

        if not records:
            return

        self.session.execute(
            self.INSERT_SQL,
            records,
        )