"""
Loading logic for customer records.

Loads validated customer records into staging.stg_customers.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


class CustomerLoader:
    """
    Load customer records into the staging layer.
    """

    INSERT_SQL = text(
        """
        INSERT INTO staging.stg_customers (
            customer_id,
            customer_name,
            contact,
            address,
            first_order_date,
            last_order_date,
            total_orders,
            total_spent,
            total_paid,
            total_due,
            status,
            source_system,
            source_table,
            source_row_identifier,
            ingestion_batch_id,
            source_hash,
            record_status,
            validation_error
        )
        VALUES (
            :customer_id,
            :customer_name,
            :contact,
            :address,
            :first_order_date,
            :last_order_date,
            :total_orders,
            :total_spent,
            :total_paid,
            :total_due,
            :status,
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
        record: dict[str, Any],
        *,
        validation_errors: list[str] | None = None,
    ) -> None:
        """
        Load a single customer record into staging.

        Records with validation errors are preserved in staging with
        record_status='invalid'. Valid records are loaded with
        record_status='pending'.
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
        """
        Load multiple already-prepared customer records into staging.

        Each record must contain all fields required by INSERT_SQL,
        including record_status and validation_error.
        """
        if not records:
            return

        self.session.execute(
            self.INSERT_SQL,
            records,
        )