"""
Loading logic for order item records.

Loads validated order item records into staging.stg_order_items.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from etl.load.base import BaseLoader


class OrderItemLoader(BaseLoader):
    """Load order item records into the staging layer."""

    INSERT_SQL = text(
        """
        INSERT INTO staging.stg_order_items (
            order_item_id,
            order_id,
            product_id,
            stock_location_id,
            quantity,
            unit_price,
            cost_price,
            line_amount,
            item_discount,
            cogs,
            source_system,
            source_table,
            source_row_identifier,
            ingestion_batch_id,
            source_hash,
            record_status,
            validation_error
        )
        VALUES (
            :order_item_id,
            :order_id,
            :product_id,
            :stock_location_id,
            :quantity,
            :unit_price,
            :cost_price,
            :line_amount,
            :item_discount,
            :cogs,
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
        """Load a single staging-ready order item record."""

        self.session.execute(
            self.INSERT_SQL,
            data,
        )

    def load_many(
        self,
        records: list[dict[str, Any]],
    ) -> int:
        """Load multiple order item records."""

        if not records:
            return 0

        result = self.session.execute(
            self.INSERT_SQL,
            records,
        )

        return result.rowcount or 0