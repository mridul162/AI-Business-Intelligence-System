"""
Loading logic for stock movement records.

Loads validated stock movement records into
staging.stg_stock_movements.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from etl.load.base import BaseLoader


class StockMovementLoader(BaseLoader):
    """Load stock movement records into the staging layer."""

    INSERT_SQL = text(
        """
        INSERT INTO staging.stg_stock_movements (
            movement_id,
            movement_date,
            product_id,
            from_location_id,
            to_location_id,
            movement_type,
            quantity,
            reference_id,
            notes,
            source_system,
            source_table,
            source_row_identifier,
            ingestion_batch_id,
            source_hash,
            record_status,
            validation_error,
            direction,
            source_created_at
        )
        VALUES (
            :movement_id,
            :movement_date,
            :product_id,
            :from_location_id,
            :to_location_id,
            :movement_type,
            :quantity,
            :reference_id,
            :notes,
            :source_system,
            :source_table,
            :source_row_identifier,
            :ingestion_batch_id,
            :source_hash,
            :record_status,
            :validation_error,
            :direction,
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
        """Load one stock movement record."""

        self.session.execute(
            self.INSERT_SQL,
            data,
        )

    def load_many(
        self,
        records: list[dict[str, Any]],
    ) -> None:
        """Load multiple stock movement records."""

        if not records:
            return

        self.session.execute(
            self.INSERT_SQL,
            records,
        )