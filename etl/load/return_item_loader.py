"""
Loading logic for return item records.

Loads transformed return item records into staging.stg_return_items.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from etl.load.base import BaseLoader


class ReturnItemLoader(BaseLoader):
    """
    Load return item records into the staging layer.
    """

    INSERT_SQL = text(
        """
        INSERT INTO staging.stg_return_items (
            return_item_id,
            return_id,
            order_item_id,
            product_id,
            quantity,
            unit_price,
            amount,
            source_system,
            source_table,
            source_row_identifier,
            ingestion_batch_id,
            source_hash,
            record_status,
            validation_error
        )
        VALUES (
            :return_item_id,
            :return_id,
            :order_item_id,
            :product_id,
            :quantity,
            :unit_price,
            :amount,
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
        DO NOTHING
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