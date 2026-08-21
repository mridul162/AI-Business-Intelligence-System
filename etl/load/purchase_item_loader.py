"""
Loading logic for purchase item records.

Loads validated purchase item records into staging.stg_purchase_items.

Note: raw.purchase_items uses the column names `discount` and
`line_total`, while staging.stg_purchase_items names the equivalent
columns `item_discount` and `line_amount`. PurchaseItemTransformer is
responsible for renaming these fields during transformation; this
loader simply writes whatever keys the transformed record dict
contains into the matching bind parameters.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from etl.load.base import BaseLoader


class PurchaseItemLoader(BaseLoader):
    """Load purchase item records into the staging layer."""

    INSERT_SQL = text(
        """
        INSERT INTO staging.stg_purchase_items (
            purchase_item_id,
            purchase_id,
            product_id,
            stock_location_id,
            quantity,
            unit_cost,
            line_amount,
            item_discount,
            source_system,
            source_table,
            source_row_identifier,
            ingestion_batch_id,
            source_hash,
            record_status,
            validation_error
        )
        VALUES (
            :purchase_item_id,
            :purchase_id,
            :product_id,
            :stock_location_id,
            :quantity,
            :unit_cost,
            :line_amount,
            :item_discount,
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
        """Load one purchase item record."""

        self.session.execute(
            self.INSERT_SQL,
            data,
        )

    def load_many(
        self,
        records: list[dict[str, Any]],
    ) -> None:
        """Load multiple purchase item records."""

        if not records:
            return

        self.session.execute(
            self.INSERT_SQL,
            records,
        )