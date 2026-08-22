"""
Loader for the core.dim_location warehouse dimension.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session


class LocationDimensionLoader:
    """
    Load stock location master data from staging.stg_stock_locations
    into core.dim_location.

    Unlike the other simple dimensions, dim_location stores a
    partner_key foreign key rather than the natural partner_id, so
    the load resolves partner_id to partner_key via core.dim_partner.
    """

    UPSERT_SQL = text(
        """
        INSERT INTO core.dim_location (
            stock_location_id,
            location_name,
            location_type,
            partner_key,
            active
        )
        SELECT
            sl.stock_location_id,
            sl.location_name,
            sl.location_type,
            p.partner_key,
            sl.active
        FROM staging.stg_stock_locations AS sl
        LEFT JOIN core.dim_partner AS p
            ON p.partner_id = sl.partner_id
        WHERE sl.record_status = 'pending'
        ON CONFLICT (stock_location_id)
        DO UPDATE SET
            location_name = EXCLUDED.location_name,
            location_type = EXCLUDED.location_type,
            partner_key = EXCLUDED.partner_key,
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
        Load stock location records from staging into the core
        dimension.

        New locations are inserted. Existing locations are updated
        using stock_location_id as the business key. partner_id is
        resolved to core.dim_partner.partner_key via a lookup join;
        locations whose partner_id has no matching partner are loaded
        with a NULL partner_key rather than being dropped.

        Note:
            This loader assumes core.dim_partner has already been
            loaded for the current batch, since partner_key is
            resolved by joining against it.

        Returns:
            Number of rows inserted or updated.
        """

        result = self.session.execute(
            self.UPSERT_SQL
        )

        return int(getattr(result, "rowcount", 0) or 0)