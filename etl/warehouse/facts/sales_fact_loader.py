"""
Warehouse loader for the sales fact table.

Loads validated order line items from staging.stg_order_items into
core.fact_sales and resolves warehouse dimension keys.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session


class SalesFactLoader:
    """Load order line items from staging into core.fact_sales."""

    LOAD_SQL = text(
        """
        INSERT INTO core.fact_sales (
            order_id,
            order_item_id,
            date_key,
            customer_key,
            product_key,
            location_key,
            quantity,
            unit_price,
            item_discount,
            line_total,
            gross_sales,
            unit_cost,
            cogs,
            source_system,
            source_table,
            source_row_identifier,
            ingestion_batch_id,
            ingested_at
        )
        SELECT
            stg.order_id,
            stg.order_item_id,
            fo.date_key,
            fo.customer_key,
            p.product_key,
            l.location_key,
            stg.quantity,
            COALESCE(stg.unit_price, 0),
            COALESCE(stg.item_discount, 0),
            COALESCE(
                stg.line_amount,
                (stg.quantity * COALESCE(stg.unit_price, 0))
                    - COALESCE(stg.item_discount, 0)
            ),
            stg.quantity * COALESCE(stg.unit_price, 0),
            COALESCE(stg.cost_price, 0),
            COALESCE(
                stg.cogs,
                stg.quantity * COALESCE(stg.cost_price, 0)
            ),
            stg.source_system,
            stg.source_table,
            stg.source_row_identifier,
            stg.ingestion_batch_id,
            stg.ingested_at
        FROM (
            SELECT DISTINCT ON (order_item_id)
                *
            FROM staging.stg_order_items
            WHERE record_status = 'pending'
            ORDER BY
                order_item_id,
                ingested_at DESC,
                stg_order_item_id DESC
        ) AS stg
        INNER JOIN core.fact_orders AS fo
            ON fo.order_id = stg.order_id
        INNER JOIN core.dim_product AS p
            ON p.product_id = stg.product_id
        INNER JOIN core.dim_location AS l
            ON l.stock_location_id = stg.stock_location_id

        ON CONFLICT (order_item_id)
        DO UPDATE SET
            date_key = EXCLUDED.date_key,
            customer_key = EXCLUDED.customer_key,
            product_key = EXCLUDED.product_key,
            location_key = EXCLUDED.location_key,
            quantity = EXCLUDED.quantity,
            unit_price = EXCLUDED.unit_price,
            item_discount = EXCLUDED.item_discount,
            line_total = EXCLUDED.line_total,
            gross_sales = EXCLUDED.gross_sales,
            unit_cost = EXCLUDED.unit_cost,
            cogs = EXCLUDED.cogs,
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
        Load pending staging order items into the warehouse as sales.

        Existing sales rows are updated (matched on order_item_id),
        making the load idempotent.

        Dimension resolution:
            - date_key and customer_key are pulled from the already
              loaded core.fact_orders row for the item's order_id,
              rather than re-resolved from a date/customer here.
            - product_key is resolved from core.dim_product via
              product_id.
            - location_key is resolved from core.dim_location via
              stock_location_id.

        Because date_key, product_key, and location_key are all
        NOT NULL on core.fact_sales, the joins above are INNER JOINs:
        a staging item whose order, product, or location cannot be
        resolved is silently excluded from this load rather than
        failing it. customer_key remains nullable and is passed
        through as-is from core.fact_orders.

        Note:
            This loader assumes core.fact_orders, core.dim_product,
            and core.dim_location have already been loaded for the
            current batch, since all three are resolved via joins.

        Returns:
            Number of rows inserted or updated.
        """

        result = self.session.execute(
            self.LOAD_SQL
        )

        return int(getattr(result, "rowcount", 0) or 0)