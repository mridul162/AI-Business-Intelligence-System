"""
Loading logic for supplier records.

Loads validated supplier records into staging.stg_suppliers.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from etl.load.base import BaseLoader


class SupplierLoader(BaseLoader):
    """Load supplier records into the staging layer."""

    INSERT_SQL = text(
        """
        INSERT INTO staging.stg_suppliers (
            supplier_id,
            supplier_name,
            contact,
            address,
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
            :supplier_id,
            :supplier_name,
            :contact,
            :address,
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
        """Load one return record."""

        self.session.execute(
            self.INSERT_SQL,
            data,
        )

    def load_many(
        self,
        records: list[dict[str, Any]],
    ) -> None:
        """Load multiple return records."""

        if not records:
            return

        self.session.execute(
            self.INSERT_SQL,
            records,
        )