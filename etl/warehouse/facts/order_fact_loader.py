"""
Warehouse loader for the orders fact table.

Loads validated order records from staging.stg_orders into
core.fact_orders and resolves warehouse dimension keys.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session


class OrderFactLoader:
    """Load orders from staging into core.fact_orders."""

    LOAD_SQL = text(
        """
        INSERT INTO core.fact_orders (
            order_id,
            date_key,
            customer_key,
            subtotal,
            invoice_discount,
            delivery_charge,
            total_amount,
            order_status,
            collected_by,
            source_created_at,
            source_system,
            source_table,
            source_row_identifier,
            ingestion_batch_id,
            ingested_at
        )
        SELECT
            stg.order_id,
            d.date_key,
            c.customer_key,
            COALESCE(stg.subtotal, 0),
            COALESCE(stg.discount, 0),
            COALESCE(stg.delivery_charge, 0),
            COALESCE(stg.total_amount, 0),
            COALESCE(stg.order_status, 'unknown'),
            stg.collected_by,
            stg.source_created_at,
            stg.source_system,
            stg.source_table,
            stg.source_row_identifier,
            stg.ingestion_batch_id,
            stg.ingested_at
        FROM (
            SELECT DISTINCT ON (order_id)
                *
            FROM staging.stg_orders
            WHERE record_status = 'pending'
            ORDER BY
                order_id,
                ingested_at DESC,
                stg_order_id DESC
        ) AS stg
        INNER JOIN core.dim_date AS d
            ON d.date = stg.order_date
        LEFT JOIN core.dim_customer AS c
            ON c.customer_id = stg.customer_id
            AND c.is_current = TRUE

        ON CONFLICT (order_id)
        DO UPDATE SET
            date_key = EXCLUDED.date_key,
            customer_key = EXCLUDED.customer_key,
            subtotal = EXCLUDED.subtotal,
            invoice_discount = EXCLUDED.invoice_discount,
            delivery_charge = EXCLUDED.delivery_charge,
            total_amount = EXCLUDED.total_amount,
            order_status = EXCLUDED.order_status,
            collected_by = EXCLUDED.collected_by,
            source_created_at = EXCLUDED.source_created_at,
            source_system = EXCLUDED.source_system,
            source_table = EXCLUDED.source_table,
            source_row_identifier = EXCLUDED.source_row_identifier,
            ingestion_batch_id = EXCLUDED.ingestion_batch_id,
            ingested_at = EXCLUDED.ingested_at;
        """
    )

    def __init__(
        self,
        session: Session,
    ) -> None:
        self.session = session

    def load(self) -> int:
        """
        Load pending staging orders into the warehouse.

        Existing orders are updated, making the load idempotent.
        """

        result = self.session.execute(
            self.LOAD_SQL
        )

        return int(getattr(result, "rowcount", 0) or 0)