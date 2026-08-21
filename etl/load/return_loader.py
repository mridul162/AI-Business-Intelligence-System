"""
Loading logic for return records.

Loads validated return records into staging.stg_returns.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from etl.load.base import BaseLoader


class ReturnLoader(BaseLoader):
    """Load return records into the staging layer."""

    INSERT_SQL = text(
        """
        INSERT INTO staging.stg_returns (
            return_id,
            return_date,
            customer_id,
            order_id,
            total_amount,
            refund_amount,
            adjustment_amount,
            return_status,
            notes,
            source_system,
            source_table,
            source_row_identifier,
            ingestion_batch_id,
            source_hash,
            record_status,
            validation_error,
            return_type,
            purchase_id,
            location_id,
            cash_account_id,
            returned_by,
            reason,
            source_created_at
        )
        VALUES (
            :return_id,
            :return_date,
            :customer_id,
            :order_id,
            :total_amount,
            :refund_amount,
            :adjustment_amount,
            :return_status,
            :notes,
            :source_system,
            :source_table,
            :source_row_identifier,
            :ingestion_batch_id,
            :source_hash,
            :record_status,
            :validation_error,
            :return_type,
            :purchase_id,
            :location_id,
            :cash_account_id,
            :returned_by,
            :reason,
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