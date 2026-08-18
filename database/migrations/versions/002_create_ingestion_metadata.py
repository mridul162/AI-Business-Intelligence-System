"""create ingestion metadata (raw.ingestion_batches, raw.ingestion_errors)

Revision ID: 002_create_ingestion_metadata
Revises: 001_create_schemas
Create Date: 2026-08-17

Establishes the ingestion lineage/tracking infrastructure that every
later raw/staging/core load depends on, before any HBMS-shaped tables
exist. Corresponds to the ORM models in database/models/raw.py
(IngestionBatch, IngestionError).

    raw.ingestion_batches
        one row per ingestion run: what source was loaded, when, whether
        it succeeded, and how many records were received/loaded/rejected.

    raw.ingestion_errors
        one row per quarantined/rejected source record within a batch,
        with the offending payload preserved for inspection and replay.

See POSTGRESQL_SCHEMA.md section 4 (Common Lineage Columns) and
section 33 (Handling Source Corrections) for the rationale.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "002_ingestion_metadata"
down_revision: Union[str, None] = "001_schemas"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

BATCH_STATUSES = (
    "running",
    "completed",
    "failed",
    "partially_completed",
)


def upgrade() -> None:
    op.create_table(
        "ingestion_batches",
        sa.Column(
            "ingestion_batch_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("source_system", sa.Text(), nullable=False),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("source_reference", sa.Text(), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.Text(),
            server_default=sa.text("'running'"),
            nullable=False,
        ),
        sa.Column("records_received", sa.Integer(), nullable=True),
        sa.Column("records_loaded", sa.Integer(), nullable=True),
        sa.Column("records_rejected", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        # Pass only the bare constraint name — Alembic re-applies the
        # naming convention's "ck_%(table_name)s_%(constraint_name)s"
        # pattern on top of whatever name is given, so a pre-prefixed
        # name here would double up (caught via `upgrade head --sql`).
        sa.CheckConstraint(
            f"status IN {BATCH_STATUSES!r}",
            name="status_valid",
        ),
        sa.PrimaryKeyConstraint("ingestion_batch_id", name="pk_ingestion_batches"),
        schema="raw",
    )
    op.create_index(
        "ix_ingestion_batches_status",
        "ingestion_batches",
        ["status"],
        schema="raw",
    )
    op.create_index(
        "ix_ingestion_batches_started_at",
        "ingestion_batches",
        ["started_at"],
        schema="raw",
    )

    op.create_table(
        "ingestion_errors",
        sa.Column(
            "error_id",
            sa.BigInteger(),
            sa.Identity(always=True),
            nullable=False,
        ),
        sa.Column("ingestion_batch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_table", sa.Text(), nullable=False),
        sa.Column("source_row_identifier", sa.Text(), nullable=True),
        sa.Column("error_type", sa.Text(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_batch_id"],
            ["raw.ingestion_batches.ingestion_batch_id"],
            name="fk_ingestion_errors_ingestion_batch_id_ingestion_batches",
        ),
        sa.PrimaryKeyConstraint("error_id", name="pk_ingestion_errors"),
        schema="raw",
    )
    op.create_index(
        "ix_ingestion_errors_ingestion_batch_id",
        "ingestion_errors",
        ["ingestion_batch_id"],
        schema="raw",
    )
    op.create_index(
        "ix_ingestion_errors_source_table",
        "ingestion_errors",
        ["source_table"],
        schema="raw",
    )


def downgrade() -> None:
    # Children before parent: ingestion_errors FKs to ingestion_batches.
    op.drop_index("ix_ingestion_errors_source_table", table_name="ingestion_errors", schema="raw")
    op.drop_index(
        "ix_ingestion_errors_ingestion_batch_id", table_name="ingestion_errors", schema="raw"
    )
    op.drop_table("ingestion_errors", schema="raw")

    op.drop_index("ix_ingestion_batches_started_at", table_name="ingestion_batches", schema="raw")
    op.drop_index("ix_ingestion_batches_status", table_name="ingestion_batches", schema="raw")
    op.drop_table("ingestion_batches", schema="raw")
