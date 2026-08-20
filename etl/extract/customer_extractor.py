from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from etl.extract.base import BaseExtractor


class CustomerExtractor(BaseExtractor):
    """Extract customer records from the raw layer."""

    def extract(
        self,
        session: Session,
        batch_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Extract customer records from raw.customers.

        Currently performs a full extraction. Batch-based incremental
        filtering can be implemented later when the incremental ETL
        strategy is finalized.
        """

        query = text(
            """
            SELECT *
            FROM raw.customers
            ORDER BY customer_id
            """
        )

        result = session.execute(query)

        return [
            dict(row._mapping)
            for row in result
        ]