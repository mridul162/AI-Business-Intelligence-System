"""
Loading logic for product records.

Loads validated product records into staging.stg_products.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from etl.load.base import BaseLoader


class ProductLoader(BaseLoader):
    """
    Load product records into the staging layer.
    """

    INSERT_SQL = text(
        """
        INSERT INTO staging.stg_products (
            product_id,
            product_name,
            category,
            unit,
            selling_price,
            cost_price,
            opening_stock,
            reorder_level,
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
            :product_id,
            :product_name,
            :category,
            :unit,
            :selling_price,
            :cost_price,
            :opening_stock,
            :reorder_level,
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

    def __init__(self, session: Session) -> None:
        """
        Initialize the loader with an active database session.
        """
        self.session = session

    def load(
        self,
        data: dict[str, Any],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Load a single prepared product record into staging.stg_products.

        The record is expected to already contain all required staging
        fields, including record_status and validation_error.
        """
        self.session.execute(
            self.INSERT_SQL,
            data,
        )

    def load_many(
        self,
        records: list[dict[str, Any]],
    ) -> None:
        """
        Load multiple prepared product records into staging.stg_products.

        Each record must contain all fields required by INSERT_SQL.
        """
        if not records:
            return

        self.session.execute(
            self.INSERT_SQL,
            records,
        )