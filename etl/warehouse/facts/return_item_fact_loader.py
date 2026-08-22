"""
Warehouse loader for the return items fact table.

Loads validated return line items from staging.stg_return_items into
core.fact_return_items and resolves warehouse dimension keys.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session


class ReturnItemFactLoader:
    """Load return line items from staging into core.fact_return_items."""

    LOAD_SQL = text(
        """
        INSERT INTO core.fact_return_items (
            return_item_id,
            return_id,
            product_key,
            quantity,
            unit_price,
            line_amount,
            returned_cogs,
            source_system,
            source_table,
            source_row_identifier,
            ingestion_batch_id,
            ingested_at
        )
        SELECT
            stg.return_item_id,
            stg.return_id,
            p.product_key,
            stg.quantity,
            COALESCE(stg.unit_price, 0),
            COALESCE(
                stg.amount,
                stg.quantity * COALESCE(stg.unit_price, 0)
            ),
            COALESCE(
                stg.quantity * (fs.cogs / NULLIF(fs.quantity, 0)),
                stg.quantity * p.current_cost_price,
                0
            ),
            stg.source_system,
            stg.source_table,
            stg.source_row_identifier,
            stg.ingestion_batch_id,
            stg.ingested_at
        FROM (
            SELECT DISTINCT ON (return_item_id)
                *
            FROM staging.stg_return_items
            WHERE record_status = 'pending'
            ORDER BY
                return_item_id,
                ingested_at DESC,
                stg_return_item_id DESC
        ) AS stg
        INNER JOIN core.fact_returns AS fr
            ON fr.return_id = stg.return_id
        INNER JOIN core.dim_product AS p
            ON p.product_id = stg.product_id
        LEFT JOIN core.fact_sales AS fs
            ON fs.order_item_id = stg.order_item_id

        ON CONFLICT (return_item_id)
        DO UPDATE SET
            return_id = EXCLUDED.return_id,
            product_key = EXCLUDED.product_key,
            quantity = EXCLUDED.quantity,
            unit_price = EXCLUDED.unit_price,
            line_amount = EXCLUDED.line_amount,
            returned_cogs = EXCLUDED.returned_cogs,
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
        Load pending staging return items into the warehouse.

        Existing return items are updated (matched on
        return_item_id), making the load idempotent.

        Dimension resolution:
            - return_id must already exist in core.fact_returns
              (INNER JOIN; enforced by a foreign key on the fact
              table). A return item whose parent return hasn't been
              loaded yet is excluded from this load rather than
              failing it.
            - product_key is resolved from core.dim_product via
              product_id (INNER JOIN; required, NOT NULL).

        returned_cogs estimation:
            staging.stg_return_items carries no cost information at
            all, so returned_cogs is estimated rather than sourced
            directly, using the best available signal in this order:
                1. The original sale's per-unit COGS (from
                   core.fact_sales, matched via order_item_id),
                   scaled by the returned quantity. This is the most
                   accurate option when the return item references
                   the original order item.
                2. The product's current cost price (from
                   core.dim_product), scaled by the returned
                   quantity, if no matching original sale is found.
                3. Zero, if neither is available.
            Because option 2 uses today's cost rather than the
            cost at the time of the original sale, returned_cogs for
            older returns may not exactly reverse the COGS recognized
            in fact_sales. Please confirm this approximation is
            acceptable, or supply a staging cost column if precise
            reversal is required.

        Returns:
            Number of rows inserted or updated.
        """

        result = self.session.execute(
            self.LOAD_SQL
        )

        return int(getattr(result, "rowcount", 0) or 0)