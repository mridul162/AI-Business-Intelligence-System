"""reconcile raw and staging pipeline mappings

Revision ID: 008_reconcile_pipeline_mappings
Revises: 007_analytics_tables
Create Date: 2026-08-19

Adds only columns/tables needed to preserve source fields that are used
by the documented core model or the captured HBMS business logic.
Existing migrations are already applied in the local database, so these
changes are additive rather than rewriting historical revisions.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "008_reconcile_pipeline_mappings"
down_revision: Union[str, None] = "007_analytics_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _raw_lineage_columns() -> list[sa.Column]:
    return [
        sa.Column(
            "raw_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("ingestion_batch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_row_number", sa.Integer(), nullable=False),
        sa.Column("source_row_hash", sa.Text(), nullable=False),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "suppliers",
        *_raw_lineage_columns(),
        sa.Column("supplier_id", sa.Text(), nullable=True),
        sa.Column("supplier_name", sa.Text(), nullable=True),
        sa.Column("contact", sa.Text(), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("first_purchase_date", sa.Text(), nullable=True),
        sa.Column("last_purchase_date", sa.Text(), nullable=True),
        sa.Column("total_purchases", sa.Text(), nullable=True),
        sa.Column("total_paid", sa.Text(), nullable=True),
        sa.Column("total_due", sa.Text(), nullable=True),
        sa.Column("active", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["ingestion_batch_id"],
            ["raw.ingestion_batches.ingestion_batch_id"],
            name="fk_suppliers_ingestion_batch_id_ingestion_batches",
        ),
        sa.PrimaryKeyConstraint("raw_id", name="pk_suppliers"),
        schema="raw",
    )
    op.create_index("ix_suppliers_ingestion_batch_id", "suppliers", ["ingestion_batch_id"], schema="raw")
    op.create_index("ix_suppliers_source_row_number", "suppliers", ["source_row_number"], schema="raw")
    op.create_index("ix_suppliers_source_row_hash", "suppliers", ["source_row_hash"], schema="raw")
    op.create_index("ix_suppliers_supplier_id", "suppliers", ["supplier_id"], schema="raw")

    op.add_column("orders", sa.Column("collected_by", sa.Text(), nullable=True), schema="raw")
    op.add_column("purchases", sa.Column("other_charges", sa.Text(), nullable=True), schema="raw")
    op.add_column("purchases", sa.Column("cash_account_id", sa.Text(), nullable=True), schema="raw")
    op.add_column("purchases", sa.Column("purchased_by", sa.Text(), nullable=True), schema="raw")
    op.add_column("cash_transactions", sa.Column("created_by", sa.Text(), nullable=True), schema="raw")

    op.add_column("stg_customers", sa.Column("status", sa.Text(), nullable=True), schema="staging")
    op.add_column("stg_orders", sa.Column("collected_by", sa.Text(), nullable=True), schema="staging")
    op.add_column(
        "stg_orders",
        sa.Column("source_created_at", sa.DateTime(timezone=True), nullable=True),
        schema="staging",
    )
    op.add_column("stg_order_items", sa.Column("item_discount", sa.Numeric(14, 2), nullable=True), schema="staging")
    op.add_column("stg_order_items", sa.Column("cogs", sa.Numeric(14, 2), nullable=True), schema="staging")
    op.add_column(
        "stg_payments",
        sa.Column("source_created_at", sa.DateTime(timezone=True), nullable=True),
        schema="staging",
    )
    op.add_column("stg_purchases", sa.Column("subtotal", sa.Numeric(14, 2), nullable=True), schema="staging")
    op.add_column("stg_purchases", sa.Column("discount", sa.Numeric(14, 2), nullable=True), schema="staging")
    op.add_column("stg_purchases", sa.Column("other_charges", sa.Numeric(14, 2), nullable=True), schema="staging")
    op.add_column("stg_purchases", sa.Column("payment_method", sa.Text(), nullable=True), schema="staging")
    op.add_column("stg_purchases", sa.Column("cash_account_id", sa.String(length=50), nullable=True), schema="staging")
    op.add_column("stg_purchases", sa.Column("purchased_by", sa.Text(), nullable=True), schema="staging")
    op.add_column("stg_purchases", sa.Column("notes", sa.Text(), nullable=True), schema="staging")
    op.add_column(
        "stg_purchases",
        sa.Column("source_created_at", sa.DateTime(timezone=True), nullable=True),
        schema="staging",
    )
    op.add_column("stg_purchase_items", sa.Column("item_discount", sa.Numeric(14, 2), nullable=True), schema="staging")
    op.add_column("stg_returns", sa.Column("return_type", sa.Text(), nullable=True), schema="staging")
    op.add_column("stg_returns", sa.Column("purchase_id", sa.String(length=50), nullable=True), schema="staging")
    op.add_column("stg_returns", sa.Column("location_id", sa.String(length=50), nullable=True), schema="staging")
    op.add_column("stg_returns", sa.Column("cash_account_id", sa.String(length=50), nullable=True), schema="staging")
    op.add_column("stg_returns", sa.Column("returned_by", sa.Text(), nullable=True), schema="staging")
    op.add_column("stg_returns", sa.Column("reason", sa.Text(), nullable=True), schema="staging")
    op.add_column(
        "stg_returns",
        sa.Column("source_created_at", sa.DateTime(timezone=True), nullable=True),
        schema="staging",
    )
    op.add_column("stg_stock_movements", sa.Column("direction", sa.Text(), nullable=True), schema="staging")
    op.add_column(
        "stg_stock_movements",
        sa.Column("source_created_at", sa.DateTime(timezone=True), nullable=True),
        schema="staging",
    )
    op.add_column("stg_cash_transactions", sa.Column("direction", sa.Text(), nullable=True), schema="staging")
    op.add_column("stg_cash_transactions", sa.Column("description", sa.Text(), nullable=True), schema="staging")
    op.add_column("stg_cash_transactions", sa.Column("created_by", sa.Text(), nullable=True), schema="staging")
    op.add_column(
        "stg_cash_transactions",
        sa.Column("source_created_at", sa.DateTime(timezone=True), nullable=True),
        schema="staging",
    )
    op.add_column("stg_expenses", sa.Column("payment_method", sa.Text(), nullable=True), schema="staging")
    op.add_column("stg_expenses", sa.Column("paid_by", sa.Text(), nullable=True), schema="staging")
    op.add_column("stg_expenses", sa.Column("created_by", sa.Text(), nullable=True), schema="staging")
    op.add_column(
        "stg_expenses",
        sa.Column("source_created_at", sa.DateTime(timezone=True), nullable=True),
        schema="staging",
    )
    op.add_column("stg_partner_capital", sa.Column("capital_transaction_id", sa.String(length=50), nullable=True), schema="staging")
    op.add_column("stg_partner_capital", sa.Column("reference_id", sa.String(length=50), nullable=True), schema="staging")
    op.add_column("stg_partner_capital", sa.Column("created_by", sa.Text(), nullable=True), schema="staging")
    op.add_column(
        "stg_partner_capital",
        sa.Column("source_created_at", sa.DateTime(timezone=True), nullable=True),
        schema="staging",
    )


def downgrade() -> None:
    op.drop_column("stg_partner_capital", "source_created_at", schema="staging")
    op.drop_column("stg_partner_capital", "created_by", schema="staging")
    op.drop_column("stg_partner_capital", "reference_id", schema="staging")
    op.drop_column("stg_partner_capital", "capital_transaction_id", schema="staging")
    op.drop_column("stg_expenses", "source_created_at", schema="staging")
    op.drop_column("stg_expenses", "created_by", schema="staging")
    op.drop_column("stg_expenses", "paid_by", schema="staging")
    op.drop_column("stg_expenses", "payment_method", schema="staging")
    op.drop_column("stg_cash_transactions", "source_created_at", schema="staging")
    op.drop_column("stg_cash_transactions", "created_by", schema="staging")
    op.drop_column("stg_cash_transactions", "description", schema="staging")
    op.drop_column("stg_cash_transactions", "direction", schema="staging")
    op.drop_column("stg_stock_movements", "source_created_at", schema="staging")
    op.drop_column("stg_stock_movements", "direction", schema="staging")
    op.drop_column("stg_returns", "source_created_at", schema="staging")
    op.drop_column("stg_returns", "reason", schema="staging")
    op.drop_column("stg_returns", "returned_by", schema="staging")
    op.drop_column("stg_returns", "cash_account_id", schema="staging")
    op.drop_column("stg_returns", "location_id", schema="staging")
    op.drop_column("stg_returns", "purchase_id", schema="staging")
    op.drop_column("stg_returns", "return_type", schema="staging")
    op.drop_column("stg_purchase_items", "item_discount", schema="staging")
    op.drop_column("stg_purchases", "source_created_at", schema="staging")
    op.drop_column("stg_purchases", "notes", schema="staging")
    op.drop_column("stg_purchases", "purchased_by", schema="staging")
    op.drop_column("stg_purchases", "cash_account_id", schema="staging")
    op.drop_column("stg_purchases", "payment_method", schema="staging")
    op.drop_column("stg_purchases", "other_charges", schema="staging")
    op.drop_column("stg_purchases", "discount", schema="staging")
    op.drop_column("stg_purchases", "subtotal", schema="staging")
    op.drop_column("stg_payments", "source_created_at", schema="staging")
    op.drop_column("stg_order_items", "cogs", schema="staging")
    op.drop_column("stg_order_items", "item_discount", schema="staging")
    op.drop_column("stg_orders", "source_created_at", schema="staging")
    op.drop_column("stg_orders", "collected_by", schema="staging")
    op.drop_column("stg_customers", "status", schema="staging")
    op.drop_column("cash_transactions", "created_by", schema="raw")
    op.drop_column("purchases", "purchased_by", schema="raw")
    op.drop_column("purchases", "cash_account_id", schema="raw")
    op.drop_column("purchases", "other_charges", schema="raw")
    op.drop_column("orders", "collected_by", schema="raw")
    op.drop_index("ix_suppliers_supplier_id", table_name="suppliers", schema="raw")
    op.drop_index("ix_suppliers_source_row_hash", table_name="suppliers", schema="raw")
    op.drop_index("ix_suppliers_source_row_number", table_name="suppliers", schema="raw")
    op.drop_index("ix_suppliers_ingestion_batch_id", table_name="suppliers", schema="raw")
    op.drop_table("suppliers", schema="raw")
