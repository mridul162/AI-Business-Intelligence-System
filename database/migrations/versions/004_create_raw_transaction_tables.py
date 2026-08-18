"""
create raw transaction tables

Revision ID: 004_create_raw_transaction_tables
Revises: 003_create_raw_reference_tables
Create Date: 2026-08-18

Creates the source-oriented raw transactional tables for the HBMS.

Tables:
    raw.orders
    raw.order_items
    raw.payments
    raw.purchases
    raw.purchase_items
    raw.returns
    raw.return_items
    raw.stock_movements
    raw.cash_transactions
    raw.expenses
    raw.partner_capital

Raw-layer design:
    - Preserve source business values primarily as TEXT.
    - Do not enforce business foreign keys between transactional tables.
    - Every row belongs to an ingestion batch.
    - Source row number and row hash support lineage, change detection,
      replay, and troubleshooting.
    - Type conversion, normalization, enum validation, deduplication, and
      referential validation belong to the staging layer.

These tables mirror operational HBMS transaction structures. Derived
report sheets are intentionally excluded because they are reconciliation
targets rather than independent transactional sources of truth.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# Alembic revision identifiers.
revision: str = "004_raw_transaction"
down_revision: Union[str, None] = "003_raw_reference"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _raw_lineage_columns() -> list[sa.Column]:
    """Return standard lineage columns shared by raw source tables."""
    return [
        sa.Column(
            "raw_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "ingestion_batch_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "source_row_number",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "source_row_hash",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    ]


def _raw_lineage_constraints(
    table_name: str,
) -> list[sa.Constraint]:
    """Return standard PK/FK constraints for a raw source table."""
    return [
        sa.ForeignKeyConstraint(
            ["ingestion_batch_id"],
            ["raw.ingestion_batches.ingestion_batch_id"],
            name=(
                f"fk_{table_name}_ingestion_batch_id_"
                "ingestion_batches"
            ),
        ),
        sa.PrimaryKeyConstraint(
            "raw_id",
            name=f"pk_{table_name}",
        ),
    ]


def _create_raw_lineage_indexes(table_name: str) -> None:
    """Create standard ingestion and lineage indexes."""
    op.create_index(
        f"ix_{table_name}_ingestion_batch_id",
        table_name,
        ["ingestion_batch_id"],
        schema="raw",
    )

    op.create_index(
        f"ix_{table_name}_source_row_number",
        table_name,
        ["source_row_number"],
        schema="raw",
    )

    op.create_index(
        f"ix_{table_name}_source_row_hash",
        table_name,
        ["source_row_hash"],
        schema="raw",
    )


def _drop_raw_lineage_indexes(table_name: str) -> None:
    """Drop standard ingestion and lineage indexes."""
    op.drop_index(
        f"ix_{table_name}_source_row_hash",
        table_name=table_name,
        schema="raw",
    )

    op.drop_index(
        f"ix_{table_name}_source_row_number",
        table_name=table_name,
        schema="raw",
    )

    op.drop_index(
        f"ix_{table_name}_ingestion_batch_id",
        table_name=table_name,
        schema="raw",
    )


def upgrade() -> None:
    # ==========================================================
    # 1. ORDERS
    # ==========================================================
    #
    # Operational order header. Order-level discount and delivery
    # charge remain here and must not be repeated blindly at item grain.
    #
    op.create_table(
        "orders",
        *_raw_lineage_columns(),
        sa.Column("order_id", sa.Text(), nullable=True),
        sa.Column("order_date", sa.Text(), nullable=True),
        sa.Column("customer_id", sa.Text(), nullable=True),
        sa.Column("subtotal", sa.Text(), nullable=True),
        sa.Column("discount", sa.Text(), nullable=True),
        sa.Column("delivery_charge", sa.Text(), nullable=True),
        sa.Column("total_amount", sa.Text(), nullable=True),
        sa.Column("paid", sa.Text(), nullable=True),
        sa.Column("due", sa.Text(), nullable=True),
        sa.Column("payment_method", sa.Text(), nullable=True),
        sa.Column("order_status", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=True),
        *_raw_lineage_constraints("orders"),
        schema="raw",
    )

    _create_raw_lineage_indexes("orders")

    op.create_index(
        "ix_orders_order_id",
        "orders",
        ["order_id"],
        schema="raw",
    )

    op.create_index(
        "ix_orders_customer_id",
        "orders",
        ["customer_id"],
        schema="raw",
    )

    # ==========================================================
    # 2. ORDER ITEMS
    # ==========================================================
    #
    # Product-level sale records with transaction-time cost snapshots.
    #
    op.create_table(
        "order_items",
        *_raw_lineage_columns(),
        sa.Column("order_item_id", sa.Text(), nullable=True),
        sa.Column("order_id", sa.Text(), nullable=True),
        sa.Column("product_id", sa.Text(), nullable=True),
        sa.Column("quantity", sa.Text(), nullable=True),
        sa.Column("unit_price", sa.Text(), nullable=True),
        sa.Column("discount", sa.Text(), nullable=True),
        sa.Column("line_total", sa.Text(), nullable=True),
        sa.Column("cost_price", sa.Text(), nullable=True),
        sa.Column("cogs", sa.Text(), nullable=True),
        sa.Column(
            "fulfilled_from_location_id",
            sa.Text(),
            nullable=True,
        ),
        *_raw_lineage_constraints("order_items"),
        schema="raw",
    )

    _create_raw_lineage_indexes("order_items")

    op.create_index(
        "ix_order_items_order_item_id",
        "order_items",
        ["order_item_id"],
        schema="raw",
    )

    op.create_index(
        "ix_order_items_order_id",
        "order_items",
        ["order_id"],
        schema="raw",
    )

    op.create_index(
        "ix_order_items_product_id",
        "order_items",
        ["product_id"],
        schema="raw",
    )

    # ==========================================================
    # 3. PAYMENTS
    # ==========================================================
    #
    # One row per actual customer payment event.
    #
    op.create_table(
        "payments",
        *_raw_lineage_columns(),
        sa.Column("payment_id", sa.Text(), nullable=True),
        sa.Column("payment_date", sa.Text(), nullable=True),
        sa.Column("order_id", sa.Text(), nullable=True),
        sa.Column("customer_id", sa.Text(), nullable=True),
        sa.Column("amount", sa.Text(), nullable=True),
        sa.Column("payment_method", sa.Text(), nullable=True),
        sa.Column("cash_account_id", sa.Text(), nullable=True),
        sa.Column("collected_by", sa.Text(), nullable=True),
        sa.Column("cash_transaction_id", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=True),
        *_raw_lineage_constraints("payments"),
        schema="raw",
    )

    _create_raw_lineage_indexes("payments")

    op.create_index(
        "ix_payments_payment_id",
        "payments",
        ["payment_id"],
        schema="raw",
    )

    op.create_index(
        "ix_payments_order_id",
        "payments",
        ["order_id"],
        schema="raw",
    )

    op.create_index(
        "ix_payments_customer_id",
        "payments",
        ["customer_id"],
        schema="raw",
    )

    op.create_index(
        "ix_payments_cash_transaction_id",
        "payments",
        ["cash_transaction_id"],
        schema="raw",
    )

    # ==========================================================
    # 4. PURCHASES
    # ==========================================================
    #
    # Purchase header.
    #
    op.create_table(
        "purchases",
        *_raw_lineage_columns(),
        sa.Column("purchase_id", sa.Text(), nullable=True),
        sa.Column("purchase_date", sa.Text(), nullable=True),
        sa.Column("supplier_id", sa.Text(), nullable=True),
        sa.Column("subtotal", sa.Text(), nullable=True),
        sa.Column("discount", sa.Text(), nullable=True),
        sa.Column("total_amount", sa.Text(), nullable=True),
        sa.Column("paid", sa.Text(), nullable=True),
        sa.Column("due", sa.Text(), nullable=True),
        sa.Column("payment_method", sa.Text(), nullable=True),
        sa.Column("purchase_status", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=True),
        *_raw_lineage_constraints("purchases"),
        schema="raw",
    )

    _create_raw_lineage_indexes("purchases")

    op.create_index(
        "ix_purchases_purchase_id",
        "purchases",
        ["purchase_id"],
        schema="raw",
    )

    op.create_index(
        "ix_purchases_supplier_id",
        "purchases",
        ["supplier_id"],
        schema="raw",
    )

    # ==========================================================
    # 5. PURCHASE ITEMS
    # ==========================================================
    #
    # Actual confirmed structure:
    # Purchase_Item_ID
    # Purchase_ID
    # Product_ID
    # Quantity
    # Unit_Cost
    # Discount
    # Line_Total
    # Stock_Location_ID
    #
    op.create_table(
        "purchase_items",
        *_raw_lineage_columns(),
        sa.Column("purchase_item_id", sa.Text(), nullable=True),
        sa.Column("purchase_id", sa.Text(), nullable=True),
        sa.Column("product_id", sa.Text(), nullable=True),
        sa.Column("quantity", sa.Text(), nullable=True),
        sa.Column("unit_cost", sa.Text(), nullable=True),
        sa.Column("discount", sa.Text(), nullable=True),
        sa.Column("line_total", sa.Text(), nullable=True),
        sa.Column("stock_location_id", sa.Text(), nullable=True),
        *_raw_lineage_constraints("purchase_items"),
        schema="raw",
    )

    _create_raw_lineage_indexes("purchase_items")

    op.create_index(
        "ix_purchase_items_purchase_item_id",
        "purchase_items",
        ["purchase_item_id"],
        schema="raw",
    )

    op.create_index(
        "ix_purchase_items_purchase_id",
        "purchase_items",
        ["purchase_id"],
        schema="raw",
    )

    op.create_index(
        "ix_purchase_items_product_id",
        "purchase_items",
        ["product_id"],
        schema="raw",
    )

    # ==========================================================
    # 6. RETURNS
    # ==========================================================
    #
    # Return header.
    #
    # Refund_Amount is a header-level settlement value and must remain
    # distinct from Return_Items.Line_Amount.
    #
    op.create_table(
        "returns",
        *_raw_lineage_columns(),
        sa.Column("return_id", sa.Text(), nullable=True),
        sa.Column("return_date", sa.Text(), nullable=True),
        sa.Column("return_type", sa.Text(), nullable=True),
        sa.Column("reference_order_id", sa.Text(), nullable=True),
        sa.Column("reference_purchase_id", sa.Text(), nullable=True),
        sa.Column("location_id", sa.Text(), nullable=True),
        sa.Column("refund_amount", sa.Text(), nullable=True),
        sa.Column("cash_account_id", sa.Text(), nullable=True),
        sa.Column("returned_by", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=True),
        *_raw_lineage_constraints("returns"),
        schema="raw",
    )

    _create_raw_lineage_indexes("returns")

    op.create_index(
        "ix_returns_return_id",
        "returns",
        ["return_id"],
        schema="raw",
    )

    op.create_index(
        "ix_returns_reference_order_id",
        "returns",
        ["reference_order_id"],
        schema="raw",
    )

    op.create_index(
        "ix_returns_reference_purchase_id",
        "returns",
        ["reference_purchase_id"],
        schema="raw",
    )

    # ==========================================================
    # 7. RETURN ITEMS
    # ==========================================================
    #
    # Item-grain returned products.
    #
    op.create_table(
        "return_items",
        *_raw_lineage_columns(),
        sa.Column("return_item_id", sa.Text(), nullable=True),
        sa.Column("return_id", sa.Text(), nullable=True),
        sa.Column("product_id", sa.Text(), nullable=True),
        sa.Column("quantity", sa.Text(), nullable=True),
        sa.Column("unit_price", sa.Text(), nullable=True),
        sa.Column("line_amount", sa.Text(), nullable=True),
        *_raw_lineage_constraints("return_items"),
        schema="raw",
    )

    _create_raw_lineage_indexes("return_items")

    op.create_index(
        "ix_return_items_return_item_id",
        "return_items",
        ["return_item_id"],
        schema="raw",
    )

    op.create_index(
        "ix_return_items_return_id",
        "return_items",
        ["return_id"],
        schema="raw",
    )

    op.create_index(
        "ix_return_items_product_id",
        "return_items",
        ["product_id"],
        schema="raw",
    )

    # ==========================================================
    # 8. STOCK MOVEMENTS
    # ==========================================================
    #
    # Inventory ledger. Transfers, adjustments, sales, purchases and
    # returns are preserved as operational movement records.
    #
    op.create_table(
        "stock_movements",
        *_raw_lineage_columns(),
        sa.Column("movement_id", sa.Text(), nullable=True),
        sa.Column("movement_date", sa.Text(), nullable=True),
        sa.Column("product_id", sa.Text(), nullable=True),
        sa.Column("movement_type", sa.Text(), nullable=True),
        sa.Column("direction", sa.Text(), nullable=True),
        sa.Column("quantity", sa.Text(), nullable=True),
        sa.Column("from_location_id", sa.Text(), nullable=True),
        sa.Column("to_location_id", sa.Text(), nullable=True),
        sa.Column("reference_id", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=True),
        *_raw_lineage_constraints("stock_movements"),
        schema="raw",
    )

    _create_raw_lineage_indexes("stock_movements")

    op.create_index(
        "ix_stock_movements_movement_id",
        "stock_movements",
        ["movement_id"],
        schema="raw",
    )

    op.create_index(
        "ix_stock_movements_product_id",
        "stock_movements",
        ["product_id"],
        schema="raw",
    )

    op.create_index(
        "ix_stock_movements_reference_id",
        "stock_movements",
        ["reference_id"],
        schema="raw",
    )

    # ==========================================================
    # 9. CASH TRANSACTIONS
    # ==========================================================
    #
    # Cash-account movement ledger.
    #
    # Internal transfers may create paired IN/OUT rows with a shared
    # reference. They remain raw facts and are classified later.
    #
    op.create_table(
        "cash_transactions",
        *_raw_lineage_columns(),
        sa.Column("cash_transaction_id", sa.Text(), nullable=True),
        sa.Column("transaction_date", sa.Text(), nullable=True),
        sa.Column("cash_account_id", sa.Text(), nullable=True),
        sa.Column("transaction_type", sa.Text(), nullable=True),
        sa.Column("direction", sa.Text(), nullable=True),
        sa.Column("amount", sa.Text(), nullable=True),
        sa.Column("reference_type", sa.Text(), nullable=True),
        sa.Column("reference_id", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=True),
        *_raw_lineage_constraints("cash_transactions"),
        schema="raw",
    )

    _create_raw_lineage_indexes("cash_transactions")

    op.create_index(
        "ix_cash_transactions_cash_transaction_id",
        "cash_transactions",
        ["cash_transaction_id"],
        schema="raw",
    )

    op.create_index(
        "ix_cash_transactions_cash_account_id",
        "cash_transactions",
        ["cash_account_id"],
        schema="raw",
    )

    op.create_index(
        "ix_cash_transactions_reference_id",
        "cash_transactions",
        ["reference_id"],
        schema="raw",
    )

    # ==========================================================
    # 10. EXPENSES
    # ==========================================================
    #
    op.create_table(
        "expenses",
        *_raw_lineage_columns(),
        sa.Column("expense_id", sa.Text(), nullable=True),
        sa.Column("expense_date", sa.Text(), nullable=True),
        sa.Column("expense_category", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("amount", sa.Text(), nullable=True),
        sa.Column("payment_method", sa.Text(), nullable=True),
        sa.Column("paid_by", sa.Text(), nullable=True),
        sa.Column("partner_id", sa.Text(), nullable=True),
        sa.Column("cash_account_id", sa.Text(), nullable=True),
        sa.Column("reference_id", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.Column("cash_transaction_id", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=True),
        *_raw_lineage_constraints("expenses"),
        schema="raw",
    )

    _create_raw_lineage_indexes("expenses")

    op.create_index(
        "ix_expenses_expense_id",
        "expenses",
        ["expense_id"],
        schema="raw",
    )

    op.create_index(
        "ix_expenses_cash_transaction_id",
        "expenses",
        ["cash_transaction_id"],
        schema="raw",
    )

    # ==========================================================
    # 11. PARTNER CAPITAL
    # ==========================================================
    #
    # Financing/capital events remain separate from operating income and
    # expenses.
    #
    op.create_table(
        "partner_capital",
        *_raw_lineage_columns(),
        sa.Column("capital_transaction_id", sa.Text(), nullable=True),
        sa.Column("transaction_date", sa.Text(), nullable=True),
        sa.Column("partner_id", sa.Text(), nullable=True),
        sa.Column("cash_account_id", sa.Text(), nullable=True),
        sa.Column("transaction_type", sa.Text(), nullable=True),
        sa.Column("amount", sa.Text(), nullable=True),
        sa.Column("reference_id", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.Column("cash_transaction_id", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=True),
        *_raw_lineage_constraints("partner_capital"),
        schema="raw",
    )

    _create_raw_lineage_indexes("partner_capital")

    op.create_index(
        "ix_partner_capital_capital_transaction_id",
        "partner_capital",
        ["capital_transaction_id"],
        schema="raw",
    )

    op.create_index(
        "ix_partner_capital_partner_id",
        "partner_capital",
        ["partner_id"],
        schema="raw",
    )

    op.create_index(
        "ix_partner_capital_cash_transaction_id",
        "partner_capital",
        ["cash_transaction_id"],
        schema="raw",
    )


def downgrade() -> None:
    # Reverse creation order.

    # ==========================================================
    # PARTNER CAPITAL
    # ==========================================================
    op.drop_index(
        "ix_partner_capital_cash_transaction_id",
        table_name="partner_capital",
        schema="raw",
    )
    op.drop_index(
        "ix_partner_capital_partner_id",
        table_name="partner_capital",
        schema="raw",
    )
    op.drop_index(
        "ix_partner_capital_capital_transaction_id",
        table_name="partner_capital",
        schema="raw",
    )
    _drop_raw_lineage_indexes("partner_capital")
    op.drop_table("partner_capital", schema="raw")

    # ==========================================================
    # EXPENSES
    # ==========================================================
    op.drop_index(
        "ix_expenses_cash_transaction_id",
        table_name="expenses",
        schema="raw",
    )
    op.drop_index(
        "ix_expenses_expense_id",
        table_name="expenses",
        schema="raw",
    )
    _drop_raw_lineage_indexes("expenses")
    op.drop_table("expenses", schema="raw")

    # ==========================================================
    # CASH TRANSACTIONS
    # ==========================================================
    op.drop_index(
        "ix_cash_transactions_reference_id",
        table_name="cash_transactions",
        schema="raw",
    )
    op.drop_index(
        "ix_cash_transactions_cash_account_id",
        table_name="cash_transactions",
        schema="raw",
    )
    op.drop_index(
        "ix_cash_transactions_cash_transaction_id",
        table_name="cash_transactions",
        schema="raw",
    )
    _drop_raw_lineage_indexes("cash_transactions")
    op.drop_table("cash_transactions", schema="raw")

    # ==========================================================
    # STOCK MOVEMENTS
    # ==========================================================
    op.drop_index(
        "ix_stock_movements_reference_id",
        table_name="stock_movements",
        schema="raw",
    )
    op.drop_index(
        "ix_stock_movements_product_id",
        table_name="stock_movements",
        schema="raw",
    )
    op.drop_index(
        "ix_stock_movements_movement_id",
        table_name="stock_movements",
        schema="raw",
    )
    _drop_raw_lineage_indexes("stock_movements")
    op.drop_table("stock_movements", schema="raw")

    # ==========================================================
    # RETURN ITEMS
    # ==========================================================
    op.drop_index(
        "ix_return_items_product_id",
        table_name="return_items",
        schema="raw",
    )
    op.drop_index(
        "ix_return_items_return_id",
        table_name="return_items",
        schema="raw",
    )
    op.drop_index(
        "ix_return_items_return_item_id",
        table_name="return_items",
        schema="raw",
    )
    _drop_raw_lineage_indexes("return_items")
    op.drop_table("return_items", schema="raw")

    # ==========================================================
    # RETURNS
    # ==========================================================
    op.drop_index(
        "ix_returns_reference_purchase_id",
        table_name="returns",
        schema="raw",
    )
    op.drop_index(
        "ix_returns_reference_order_id",
        table_name="returns",
        schema="raw",
    )
    op.drop_index(
        "ix_returns_return_id",
        table_name="returns",
        schema="raw",
    )
    _drop_raw_lineage_indexes("returns")
    op.drop_table("returns", schema="raw")

    # ==========================================================
    # PURCHASE ITEMS
    # ==========================================================
    op.drop_index(
        "ix_purchase_items_product_id",
        table_name="purchase_items",
        schema="raw",
    )
    op.drop_index(
        "ix_purchase_items_purchase_id",
        table_name="purchase_items",
        schema="raw",
    )
    op.drop_index(
        "ix_purchase_items_purchase_item_id",
        table_name="purchase_items",
        schema="raw",
    )
    _drop_raw_lineage_indexes("purchase_items")
    op.drop_table("purchase_items", schema="raw")

    # ==========================================================
    # PURCHASES
    # ==========================================================
    op.drop_index(
        "ix_purchases_supplier_id",
        table_name="purchases",
        schema="raw",
    )
    op.drop_index(
        "ix_purchases_purchase_id",
        table_name="purchases",
        schema="raw",
    )
    _drop_raw_lineage_indexes("purchases")
    op.drop_table("purchases", schema="raw")

    # ==========================================================
    # PAYMENTS
    # ==========================================================
    op.drop_index(
        "ix_payments_cash_transaction_id",
        table_name="payments",
        schema="raw",
    )
    op.drop_index(
        "ix_payments_customer_id",
        table_name="payments",
        schema="raw",
    )
    op.drop_index(
        "ix_payments_order_id",
        table_name="payments",
        schema="raw",
    )
    op.drop_index(
        "ix_payments_payment_id",
        table_name="payments",
        schema="raw",
    )
    _drop_raw_lineage_indexes("payments")
    op.drop_table("payments", schema="raw")

    # ==========================================================
    # ORDER ITEMS
    # ==========================================================
    op.drop_index(
        "ix_order_items_product_id",
        table_name="order_items",
        schema="raw",
    )
    op.drop_index(
        "ix_order_items_order_id",
        table_name="order_items",
        schema="raw",
    )
    op.drop_index(
        "ix_order_items_order_item_id",
        table_name="order_items",
        schema="raw",
    )
    _drop_raw_lineage_indexes("order_items")
    op.drop_table("order_items", schema="raw")

    # ==========================================================
    # ORDERS
    # ==========================================================
    op.drop_index(
        "ix_orders_customer_id",
        table_name="orders",
        schema="raw",
    )
    op.drop_index(
        "ix_orders_order_id",
        table_name="orders",
        schema="raw",
    )
    _drop_raw_lineage_indexes("orders")
    op.drop_table("orders", schema="raw")