"""create raw/staging/core/analytics schemas

Revision ID: 001_create_schemas
Revises:
Create Date: 2026-08-17

Per POSTGRESQL_SCHEMA.md section 2.1, the database is split into four
logical layers so raw source data, normalized staging data, canonical
analytical facts/dimensions, and reporting views are never mixed in the
same namespace:

    raw       - exact source representation (lineage, replay, audit)
    staging   - normalized/validated source records
    core      - canonical dimensions and facts
    analytics - views/materialized views for BI, reporting, and the AI layer

This migration only creates the schemas themselves. No tables yet -
those come in migrations 002+, one layer at a time, per the sequence in
POSTGRESQL_SCHEMA.md section 36.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001_create_schemas"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMAS = ("raw", "staging", "core", "analytics")


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    for schema in SCHEMAS:
        op.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")


def downgrade() -> None:
    # CASCADE is intentional here only because, at this point in the
    # migration history, the schemas are guaranteed to be empty (this is
    # the very first migration). Do not copy CASCADE into later
    # downgrades without checking what would be dropped with it -
    # see POSTGRESQL_SCHEMA.md section 33 on not destructively mutating
    # loaded historical data.
    for schema in reversed(SCHEMAS):
        op.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
