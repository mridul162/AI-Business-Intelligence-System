"""
Warehouse loader for purchase facts.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session


class PurchaseFactLoader:
    """
    Load purchase-item level records into core.fact_purchases.

    Fact grain:
        One row per purchase item.
    """

    LOAD_SQL = text(
        """
        WITH latest_purchases AS (
            SELECT DISTINCT ON (purchase_id)
                *
            FROM staging.stg_purchases
            WHERE record_status = 'pending'
            ORDER BY
                purchase_id,
                ingested_at DESC,
                stg_purchase_id DESC
        ),

        latest_purchase_items AS (
            SELECT DISTINCT ON (purchase_item_id)
                *
            FROM staging.stg_purchase_items
            WHERE record_status = 'pending'
            ORDER BY
                purchase_item_id,
                ingested_at DESC,
                stg_purchase_item_id DESC
        )

        INSERT INTO core.fact_purchases (
            purchase_id,
            purchase_item_id,
            date_key,
            supplier_key,
            product_key,
            location_key,
            quantity,
            unit_cost,
            item_discount,
            line_total,
            source_system,
            source_table,
            source_row_identifier,
            ingestion_batch_id,
            ingested_at
        )
        SELECT
            pi.purchase_id,
            pi.purchase_item_id,
            d.date_key,
            s.supplier_key,
            p.product_key,
            l.location_key,
            pi.quantity,
            COALESCE(pi.unit_cost, 0),
            COALESCE(pi.item_discount, 0),
            COALESCE(pi.line_amount, 0),
            pi.source_system,
            pi.source_table,
            pi.source_row_identifier,
            pi.ingestion_batch_id,
            pi.ingested_at
        FROM latest_purchase_items AS pi

        INNER JOIN latest_purchases AS ph
            ON ph.purchase_id = pi.purchase_id

        INNER JOIN core.dim_date AS d
            ON d.date = ph.purchase_date

        INNER JOIN core.dim_supplier AS s
            ON s.supplier_id = ph.supplier_id
            AND s.active is TRUE

        INNER JOIN core.dim_product AS p
            ON p.product_id = pi.product_id
            AND p.is_current is TRUE

        INNER JOIN core.dim_location AS l
            ON l.stock_location_id = pi.stock_location_id
            AND l.active is TRUE

        ON CONFLICT (purchase_id, purchase_item_id)
        DO UPDATE SET
            date_key = EXCLUDED.date_key,
            supplier_key = EXCLUDED.supplier_key,
            product_key = EXCLUDED.product_key,
            location_key = EXCLUDED.location_key,
            quantity = EXCLUDED.quantity,
            unit_cost = EXCLUDED.unit_cost,
            item_discount = EXCLUDED.item_discount,
            line_total = EXCLUDED.line_total,
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
        Load purchase facts into the warehouse.

        Returns:
            Number of rows inserted or updated.
        """

        result = self.session.execute(
            self.LOAD_SQL
        )

        return int(getattr(result, "rowcount", 0) or 0)