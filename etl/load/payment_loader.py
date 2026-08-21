"""
Loading logic for payment records.

Loads validated payment records into staging.stg_payments.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


class PaymentLoader:
    """
    Load payment records into the staging layer.
    """

    INSERT_SQL = text(
        """
        INSERT INTO staging.stg_payments (
            payment_id,
            payment_date,
            customer_id,
            order_id,
            amount,
            payment_method,
            collected_by,
            cash_account_id,
            notes,
            source_system,
            source_table,
            source_row_identifier,
            ingestion_batch_id,
            source_hash,
            record_status,
            validation_error,
            source_created_at
        )
        VALUES (
            :payment_id,
            :payment_date,
            :customer_id,
            :order_id,
            :amount,
            :payment_method,
            :collected_by,
            :cash_account_id,
            :notes,
            :source_system,
            :source_table,
            :source_row_identifier,
            :ingestion_batch_id,
            :source_hash,
            :record_status,
            :validation_error,
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
        *,
        validation_errors: list[str] | None = None,
    ) -> None:
        """
        Load one payment record into staging.
        """

        validation_errors = validation_errors or []

        payload = {
            **record,
            "record_status": (
                "invalid"
                if validation_errors
                else "pending"
            ),
            "validation_error": (
                "; ".join(validation_errors)
                if validation_errors
                else None
            ),
        }

        self.session.execute(
            self.INSERT_SQL,
            payload,
        )

    def load_many(
        self,
        records: list[dict[str, Any]],
    ) -> None:
        """Load multiple already-prepared payment records."""

        if not records:
            return

        self.session.execute(
            self.INSERT_SQL,
            records,
        )