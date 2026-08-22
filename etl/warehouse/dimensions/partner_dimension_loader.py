"""
Loader for the core.dim_partner warehouse dimension.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session


class PartnerDimensionLoader:
    """
    Load partner master data from staging.stg_partners
    into core.dim_partner.
    """

    UPSERT_SQL = text(
        """
        INSERT INTO core.dim_partner (
            partner_id,
            partner_name,
            active
        )
        SELECT
            partner_id,
            partner_name,
            active
        FROM staging.stg_partners
        WHERE record_status = 'pending'
        ON CONFLICT (partner_id)
        DO UPDATE SET
            partner_name = EXCLUDED.partner_name,
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
        Load partner records from staging into the core dimension.

        New partners are inserted. Existing partners are updated
        using partner_id as the business key.

        Returns:
            Number of rows inserted or updated.
        """

        result = self.session.execute(
            self.UPSERT_SQL
        )

        return int(getattr(result, "rowcount", 0) or 0)