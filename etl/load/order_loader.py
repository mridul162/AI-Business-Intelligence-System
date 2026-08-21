"""
Loading logic for order records.

Loads transformed order records into staging.stg_orders.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from etl.load.base import BaseLoader


class OrderLoader(BaseLoader):
    """Load order records into the staging layer."""

    INSERT_SQL = text(
        """
        INSERT INTO staging.stg_orders (
            order_id,
            order_date,
            customer_id,
            subtotal,
            discount,
            delivery_charge,
            total_amount,
            paid_amount,
            due_amount,
            order_status,
            source_system,
            source_table,
            source_row_identifier,
            ingestion_batch_id,
            source_hash,
            record_status,
            validation_error,
            collected_by,
            source_created_at
        )
        VALUES (
            :order_id,
            :order_date,
            :customer_id,
            :subtotal,
            :discount,
            :delivery_charge,
            :total_amount,
            :paid_amount,
            :due_amount,
            :order_status,
            :source_system,
            :source_table,
            :source_row_identifier,
            :ingestion_batch_id,
            :source_hash,
            :record_status,
            :validation_error,
            :collected_by,
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
        record: dict[str, Any],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Load a single order record."""
        self.session.execute(
            self.INSERT_SQL,
            record,
        )

    def load_many(
        self,
        records: list[dict[str, Any]],
    ) -> None:
        """Load multiple order records."""
        if not records:
            return

        self.session.execute(
            self.INSERT_SQL,
            records,
        )