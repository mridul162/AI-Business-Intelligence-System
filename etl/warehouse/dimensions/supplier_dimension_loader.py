"""
Loader for the core.dim_supplier warehouse dimension.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session


class SupplierDimensionLoader:
    """
    Load supplier master data from staging.stg_suppliers
    into core.dim_supplier.
    """

    UPSERT_SQL = text(
        """
        INSERT INTO core.dim_supplier (
            supplier_id,
            supplier_name,
            contact,
            address,
            active
        )
        SELECT
            supplier_id,
            supplier_name,
            contact,
            address,
            active
        FROM staging.stg_suppliers
        WHERE record_status = 'pending'
        ON CONFLICT (supplier_id)
        DO UPDATE SET
            supplier_name = EXCLUDED.supplier_name,
            contact = EXCLUDED.contact,
            address = EXCLUDED.address,
            active = EXCLUDED.active;
        """
    )

    def __init__(
        self,
        session: Session,
    ) -> None:
        self.session = session

    def load(self) -> int:
        """
        Load supplier records from staging into the core dimension.

        New suppliers are inserted. Existing suppliers are updated
        using supplier_id as the business key.

        Returns:
            Number of rows inserted or updated.
        """

        result = self.session.execute(
            self.UPSERT_SQL
        )

        return int(getattr(result, "rowcount", 0) or 0)