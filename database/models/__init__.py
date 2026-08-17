"""
ORM models for the AI-BI analytical database.

Models are added incrementally, layer by layer, per the migration
sequence in docs/POSTGRESQL_SCHEMA.md section 36:

    001_create_schemas          <- current step (no ORM models yet)
    002_create_ingestion_metadata
    003_create_raw_tables
    004_create_staging_tables
    005_create_dimensions
    006_create_fact_orders
    ...

Each layer's models are imported here once added, so that
`Base.metadata` (see database/base.py) reflects the full schema for
Alembic autogenerate.
"""

from database.base import Base  # noqa: F401
