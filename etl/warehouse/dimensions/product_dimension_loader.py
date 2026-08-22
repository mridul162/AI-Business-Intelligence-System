"""
Loader for the core.dim_product warehouse dimension.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session


class ProductDimensionLoader:
    """
    Load product master data from staging.stg_products
    into core.dim_product.
    """

    UPSERT_SQL = text(
        """
        INSERT INTO core.dim_product (
            product_id,
            product_name,
            category,
            unit,
            current_selling_price,
            current_cost_price,
            opening_stock,
            reorder_level,
            active,
            valid_from,
            valid_to,
            is_current
        )
        SELECT
            product_id,
            product_name,
            category,
            unit,
            selling_price,
            cost_price,
            opening_stock,
            reorder_level,
            active::text,
            NOW(),
            NULL,
            TRUE
        FROM staging.stg_products
        WHERE record_status = 'pending'
        ON CONFLICT (product_id)
        DO UPDATE SET
            product_name = EXCLUDED.product_name,
            category = EXCLUDED.category,
            unit = EXCLUDED.unit,
            current_selling_price = EXCLUDED.current_selling_price,
            current_cost_price = EXCLUDED.current_cost_price,
            opening_stock = EXCLUDED.opening_stock,
            reorder_level = EXCLUDED.reorder_level,
            active = EXCLUDED.active,
            valid_to = NULL,
            is_current = TRUE;
        """
    )

    def __init__(
        self,
        session: Session,
    ) -> None:
        self.session = session

    def load(self) -> int:
        """
        Load product records from staging into the core dimension.

        New products are inserted. Existing products are updated
        using product_id as the business key.

        Returns:
            Number of rows inserted or updated.
        """

        result = self.session.execute(
            self.UPSERT_SQL
        )

        return int(getattr(result, "rowcount", 0) or 0)