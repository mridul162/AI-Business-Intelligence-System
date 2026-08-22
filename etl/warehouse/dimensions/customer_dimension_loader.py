"""
Loader for the core.dim_customer warehouse dimension.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session


class CustomerDimensionLoader:
    """
    Load customer master data from staging.stg_customers
    into core.dim_customer.
    """

    UPSERT_SQL = text(
        """
        INSERT INTO core.dim_customer (
            customer_id,
            customer_name,
            phone,
            address,
            status,
            valid_from,
            valid_to,
            is_current
        )
        SELECT
            customer_id,
            customer_name,
            contact,
            address,
            status,
            NOW(),
            NULL,
            TRUE
        FROM staging.stg_customers
        WHERE record_status = 'pending'
        ON CONFLICT (customer_id)
        DO UPDATE SET
            customer_name = EXCLUDED.customer_name,
            phone = EXCLUDED.phone,
            address = EXCLUDED.address,
            status = EXCLUDED.status,
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
        Load customer records from staging into the core dimension.

        New customers are inserted. Existing customers are updated
        using customer_id as the business key.

        Returns:
            Number of rows inserted or updated.
        """

        result = self.session.execute(
            self.UPSERT_SQL
        )

        return int(getattr(result, "rowcount", 0) or 0)