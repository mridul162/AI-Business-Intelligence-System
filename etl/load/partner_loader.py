"""
Loading logic for partner records.

Loads validated partner records into staging.stg_partners.

Note: staging.stg_partners does not have a `role` column, even though
raw.partners captures it. `role` is carried through extraction and
transformation (in case it's needed for validation or logging) but is
not persisted to staging. Extra keys in the record dict are harmless
here since SQLAlchemy's text() bindparams only consume the named
parameters that appear in the SQL string.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from etl.load.base import BaseLoader


class PartnerLoader(BaseLoader):
    """Load partner records into the staging layer."""

    INSERT_SQL = text(
        """
        INSERT INTO staging.stg_partners (
            partner_id,
            partner_name,
            active,
            source_system,
            source_table,
            source_row_identifier,
            ingestion_batch_id,
            source_hash,
            record_status,
            validation_error
        )
        VALUES (
            :partner_id,
            :partner_name,
            :active,
            :source_system,
            :source_table,
            :source_row_identifier,
            :ingestion_batch_id,
            :source_hash,
            :record_status,
            :validation_error
        )
        ON CONFLICT (
            ingestion_batch_id,
            source_table,
            source_row_identifier
        )
        DO NOTHING;
        """
    )

    def __init__(
        self,
        session: Session,
    ) -> None:
        self.session = session

    def load(
        self,
        data: dict[str, Any],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Load one partner record."""

        self.session.execute(
            self.INSERT_SQL,
            data,
        )

    def load_many(
        self,
        records: list[dict[str, Any]],
    ) -> None:
        """Load multiple partner records."""

        if not records:
            return

        self.session.execute(
            self.INSERT_SQL,
            records,
        )