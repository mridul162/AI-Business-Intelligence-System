"""
Loading logic for stock location records.

Loads validated stock location records into
staging.stg_stock_locations.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from etl.load.base import BaseLoader


class StockLocationLoader(BaseLoader):
    """Load stock location records into the staging layer."""

    INSERT_SQL = text(
        """
        INSERT INTO staging.stg_stock_locations (
            stock_location_id,
            location_name,
            location_type,
            partner_id,
            active,
            source_system,
            source_table,
            source_row_identifier,
            ingestion_batch_id,
            source_hash,
            record_status,
            validation_error
        )
        VALUES (
            :stock_location_id,
            :location_name,
            :location_type,
            :partner_id,
            :active,
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
        """Load one stock location record."""

        self.session.execute(
            self.INSERT_SQL,
            data,
        )

    def load_many(
        self,
        records: list[dict[str, Any]],
    ) -> None:
        """Load multiple stock location records."""

        if not records:
            return

        self.session.execute(
            self.INSERT_SQL,
            records,
        )