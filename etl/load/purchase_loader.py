"""
Loading logic for purchase records.

Loads validated purchase records into staging.stg_purchases.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from etl.load.base import BaseLoader


class PurchaseLoader(BaseLoader):
    """Load purchase records into the staging layer."""

    INSERT_SQL = text(
        """
        INSERT INTO staging.stg_purchases (
            purchase_id,
            purchase_date,
            supplier_id,
            total_amount,
            paid_amount,
            due_amount,
            purchase_status,
            source_system,
            source_table,
            source_row_identifier,
            ingestion_batch_id,
            source_hash,
            record_status,
            validation_error,
            subtotal,
            discount,
            other_charges,
            payment_method,
            cash_account_id,
            purchased_by,
            notes,
            source_created_at
        )
        VALUES (
            :purchase_id,
            :purchase_date,
            :supplier_id,
            :total_amount,
            :paid_amount,
            :due_amount,
            :purchase_status,
            :source_system,
            :source_table,
            :source_row_identifier,
            :ingestion_batch_id,
            :source_hash,
            :record_status,
            :validation_error,
            :subtotal,
            :discount,
            :other_charges,
            :payment_method,
            :cash_account_id,
            :purchased_by,
            :notes,
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
        """Load one purchase record."""

        self.session.execute(
            self.INSERT_SQL,
            data,
        )

    def load_many(
        self,
        records: list[dict[str, Any]],
    ) -> None:
        """Load multiple purchase records."""

        if not records:
            return

        self.session.execute(
            self.INSERT_SQL,
            records,
        )