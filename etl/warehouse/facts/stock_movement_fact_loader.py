"""
Warehouse loader for the stock movements fact table.

Loads validated stock movement records from
staging.stg_stock_movements into core.fact_stock_movements and
resolves warehouse dimension keys.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session


class StockMovementFactLoader:
    """Load stock movements from staging into core.fact_stock_movements."""

    LOAD_SQL = text(
        """
        INSERT INTO core.fact_stock_movements (
            movement_id,
            date_key,
            product_key,
            movement_type,
            direction,
            quantity,
            from_location_key,
            to_location_key,
            reference_id,
            notes,
            source_system,
            source_table,
            source_row_identifier,
            ingestion_batch_id,
            ingested_at
        )
        SELECT
            stg.movement_id,
            d.date_key,
            p.product_key,
            stg.movement_type,
            stg.direction,
            stg.quantity,
            fl.location_key,
            tl.location_key,
            stg.reference_id,
            stg.notes,
            stg.source_system,
            stg.source_table,
            stg.source_row_identifier,
            stg.ingestion_batch_id,
            stg.ingested_at
        FROM (
            SELECT DISTINCT ON (movement_id)
                *
            FROM staging.stg_stock_movements
            WHERE record_status = 'pending'
            ORDER BY
                movement_id,
                ingested_at DESC,
                stg_stock_movement_id DESC
        ) AS stg
        INNER JOIN core.dim_date AS d
            ON d.date = stg.movement_date
        INNER JOIN core.dim_product AS p
            ON p.product_id = stg.product_id
        LEFT JOIN core.dim_location AS fl
            ON fl.stock_location_id = stg.from_location_id
        LEFT JOIN core.dim_location AS tl
            ON tl.stock_location_id = stg.to_location_id

        ON CONFLICT (movement_id)
        DO UPDATE SET
            date_key = EXCLUDED.date_key,
            product_key = EXCLUDED.product_key,
            movement_type = EXCLUDED.movement_type,
            direction = EXCLUDED.direction,
            quantity = EXCLUDED.quantity,
            from_location_key = EXCLUDED.from_location_key,
            to_location_key = EXCLUDED.to_location_key,
            reference_id = EXCLUDED.reference_id,
            notes = EXCLUDED.notes,
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
        Load pending staging stock movements into the warehouse.

        Existing movements are updated (matched on movement_id),
        making the load idempotent.

        Dimension resolution:
            - date_key is resolved from core.dim_date via
              movement_date (INNER JOIN; required, NOT NULL).
            - product_key is resolved from core.dim_product via
              product_id (INNER JOIN; required, NOT NULL).
            - from_location_key and to_location_key are each resolved
              from core.dim_location, via from_location_id and
              to_location_id respectively (two separate LEFT JOINs
              against the same table). Both are nullable on the fact
              table, matching a movement that only has one side
              populated (e.g. a pure inbound receipt with no
              from_location, or a pure outbound issue with no
              to_location).

        Column notes:
            - direction is passed through as-is from staging even
              though it is nullable there but constrained to 'IN' or
              'OUT' (NOT NULL) on the fact table. A staging row with
              a null or invalid direction will fail the insert rather
              than being guessed, since misclassifying stock movement
              direction would corrupt inventory reporting.

        Returns:
            Number of rows inserted or updated.
        """

        result = self.session.execute(
            self.LOAD_SQL
        )

        return int(getattr(result, "rowcount", 0) or 0)