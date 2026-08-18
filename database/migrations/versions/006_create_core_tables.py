"""create core dimension and fact tables

Revision ID: 006_core_tables
Revises: 005_staging_tables
Create Date: 2026-08-18
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "006_core_tables"
down_revision = "005_staging_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ============================================================
    # CORE DIMENSION TABLES
    # ============================================================

    op.create_table(
        "dim_date",
        sa.Column("date_key", sa.Integer(), primary_key=True),
        sa.Column("date", sa.Date(), nullable=False, unique=True),
        sa.Column("year", sa.SmallInteger(), nullable=False),
        sa.Column("quarter", sa.SmallInteger(), nullable=False),
        sa.Column("month", sa.SmallInteger(), nullable=False),
        sa.Column("month_number", sa.SmallInteger(), nullable=False),
        sa.Column("month_name", sa.String(length=20), nullable=False),
        sa.Column("week", sa.SmallInteger(), nullable=False),
        sa.Column("day", sa.SmallInteger(), nullable=False),
        sa.Column("day_name", sa.String(length=20), nullable=False),
        sa.Column("is_weekend", sa.Boolean(), nullable=False),
        schema="core",
    )

    op.create_table(
        "dim_customer",
        sa.Column(
            "customer_key",
            sa.BigInteger(),
            sa.Identity(),
            primary_key=True,
        ),
        sa.Column("customer_id", sa.String(length=50), nullable=False, unique=True),
        sa.Column("customer_name", sa.Text(), nullable=False),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=True),
        sa.Column(
            "valid_from",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("valid_to", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "is_current",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("TRUE"),
        ),
        schema="core",
    )

    op.create_table(
        "dim_product",
        sa.Column(
            "product_key",
            sa.BigInteger(),
            sa.Identity(),
            primary_key=True,
        ),
        sa.Column("product_id", sa.String(length=50), nullable=False, unique=True),
        sa.Column("product_name", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=True),
        sa.Column("unit", sa.Text(), nullable=True),
        sa.Column("current_selling_price", sa.Numeric(14, 2), nullable=True),
        sa.Column("current_cost_price", sa.Numeric(14, 2), nullable=True),
        sa.Column("opening_stock", sa.Numeric(14, 3), nullable=True),
        sa.Column("reorder_level", sa.Numeric(14, 3), nullable=True),
        sa.Column("active", sa.Text(), nullable=True),
        sa.Column(
            "valid_from",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("valid_to", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "is_current",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("TRUE"),
        ),
        schema="core",
    )

    op.create_table(
        "dim_supplier",
        sa.Column(
            "supplier_key",
            sa.BigInteger(),
            sa.Identity(),
            primary_key=True,
        ),
        sa.Column("supplier_id", sa.String(length=50), nullable=False, unique=True),
        sa.Column("supplier_name", sa.Text(), nullable=False),
        sa.Column("contact", sa.Text(), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=True),
        schema="core",
    )

    op.create_table(
        "dim_partner",
        sa.Column(
            "partner_key",
            sa.BigInteger(),
            sa.Identity(),
            primary_key=True,
        ),
        sa.Column("partner_id", sa.String(length=50), nullable=False, unique=True),
        sa.Column("partner_name", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=True),
        schema="core",
    )

    op.create_table(
        "dim_location",
        sa.Column(
            "location_key",
            sa.BigInteger(),
            sa.Identity(),
            primary_key=True,
        ),
        sa.Column(
            "stock_location_id",
            sa.String(length=50),
            nullable=False,
            unique=True,
        ),
        sa.Column("location_name", sa.Text(), nullable=False),
        sa.Column("location_type", sa.Text(), nullable=True),
        sa.Column("partner_key", sa.BigInteger(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(
            ["partner_key"],
            ["core.dim_partner.partner_key"],
        ),
        schema="core",
    )

    op.create_table(
        "dim_cash_account",
        sa.Column(
            "cash_account_key",
            sa.BigInteger(),
            sa.Identity(),
            primary_key=True,
        ),
        sa.Column(
            "cash_account_id",
            sa.String(length=50),
            nullable=False,
            unique=True,
        ),
        sa.Column("account_name", sa.Text(), nullable=False),
        sa.Column("account_type", sa.Text(), nullable=True),
        sa.Column("owner_id", sa.String(length=50), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=True),
        schema="core",
    )

    # ============================================================
    # CORE FACT TABLES
    # ============================================================

    op.create_table(
        "fact_orders",
        sa.Column("order_key", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("order_id", sa.String(length=50), nullable=False, unique=True),
        sa.Column("date_key", sa.Integer(), nullable=False),
        sa.Column("customer_key", sa.BigInteger(), nullable=True),
        sa.Column("subtotal", sa.Numeric(14, 2), nullable=False),
        sa.Column(
            "invoice_discount",
            sa.Numeric(14, 2),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "delivery_charge",
            sa.Numeric(14, 2),
            nullable=False,
            server_default="0",
        ),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("order_status", sa.Text(), nullable=False),
        sa.Column("collected_by", sa.Text(), nullable=True),
        sa.Column("source_created_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("source_system", sa.Text(), nullable=False),
        sa.Column("source_table", sa.Text(), nullable=False),
        sa.Column("source_row_identifier", sa.Text(), nullable=True),
        sa.Column("ingestion_batch_id", sa.UUID(), nullable=False),
        sa.Column(
            "ingested_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["date_key"],
            ["core.dim_date.date_key"],
        ),
        sa.ForeignKeyConstraint(
            ["customer_key"],
            ["core.dim_customer.customer_key"],
        ),
        sa.CheckConstraint(
            "subtotal >= 0",
            name="subtotal_non_negative",
        ),
        sa.CheckConstraint(
            "invoice_discount >= 0",
            name="invoice_discount_non_negative",
        ),
        sa.CheckConstraint(
            "delivery_charge >= 0",
            name="delivery_charge_non_negative",
        ),
        sa.CheckConstraint(
            "total_amount >= 0",
            name="total_amount_non_negative",
        ),
        schema="core",
    )

    op.create_table(
        "fact_sales",
        sa.Column("sales_key", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("order_id", sa.String(length=50), nullable=False),
        sa.Column(
            "order_item_id",
            sa.String(length=50),
            nullable=False,
            unique=True,
        ),
        sa.Column("date_key", sa.Integer(), nullable=False),
        sa.Column("customer_key", sa.BigInteger(), nullable=True),
        sa.Column("product_key", sa.BigInteger(), nullable=False),
        sa.Column("location_key", sa.BigInteger(), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=False),
        sa.Column(
            "item_discount",
            sa.Numeric(14, 2),
            nullable=False,
            server_default="0",
        ),
        sa.Column("line_total", sa.Numeric(14, 2), nullable=False),
        sa.Column("gross_sales", sa.Numeric(14, 2), nullable=False),
        sa.Column("unit_cost", sa.Numeric(14, 2), nullable=False),
        sa.Column("cogs", sa.Numeric(14, 2), nullable=False),
        sa.Column("source_system", sa.Text(), nullable=False),
        sa.Column("source_table", sa.Text(), nullable=False),
        sa.Column("source_row_identifier", sa.Text(), nullable=True),
        sa.Column("ingestion_batch_id", sa.UUID(), nullable=False),
        sa.Column(
            "ingested_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["date_key"], ["core.dim_date.date_key"]),
        sa.ForeignKeyConstraint(
            ["customer_key"],
            ["core.dim_customer.customer_key"],
        ),
        sa.ForeignKeyConstraint(
            ["product_key"],
            ["core.dim_product.product_key"],
        ),
        sa.ForeignKeyConstraint(
            ["location_key"],
            ["core.dim_location.location_key"],
        ),
        sa.UniqueConstraint("order_id", "order_item_id"),
        schema="core",
    )

    op.create_table(
        "fact_payments",
        sa.Column("payment_key", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("payment_id", sa.String(length=50), nullable=False, unique=True),
        sa.Column("date_key", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.String(length=50), nullable=False),
        sa.Column("customer_key", sa.BigInteger(), nullable=True),
        sa.Column("cash_account_key", sa.BigInteger(), nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("payment_method", sa.Text(), nullable=False),
        sa.Column("collected_by", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("source_created_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("source_system", sa.Text(), nullable=False),
        sa.Column("source_table", sa.Text(), nullable=False),
        sa.Column("source_row_identifier", sa.Text(), nullable=True),
        sa.Column("ingestion_batch_id", sa.UUID(), nullable=False),
        sa.Column(
            "ingested_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["date_key"], ["core.dim_date.date_key"]),
        sa.ForeignKeyConstraint(
            ["customer_key"],
            ["core.dim_customer.customer_key"],
        ),
        sa.ForeignKeyConstraint(
            ["cash_account_key"],
            ["core.dim_cash_account.cash_account_key"],
        ),
        sa.CheckConstraint(
            "amount >= 0",
            name="amount_non_negative",
        ),
        schema="core",
    )

    op.create_table(
        "fact_purchases",
        sa.Column("purchase_key", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("purchase_id", sa.String(length=50), nullable=False),
        sa.Column(
            "purchase_item_id",
            sa.String(length=50),
            nullable=False,
            unique=True,
        ),
        sa.Column("date_key", sa.Integer(), nullable=False),
        sa.Column("supplier_key", sa.BigInteger(), nullable=False),
        sa.Column("product_key", sa.BigInteger(), nullable=False),
        sa.Column("location_key", sa.BigInteger(), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit_cost", sa.Numeric(14, 2), nullable=False),
        sa.Column(
            "item_discount",
            sa.Numeric(14, 2),
            nullable=False,
            server_default="0",
        ),
        sa.Column("line_total", sa.Numeric(14, 2), nullable=False),
        sa.Column("source_system", sa.Text(), nullable=False),
        sa.Column("source_table", sa.Text(), nullable=False),
        sa.Column("source_row_identifier", sa.Text(), nullable=True),
        sa.Column("ingestion_batch_id", sa.UUID(), nullable=False),
        sa.Column(
            "ingested_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["date_key"], ["core.dim_date.date_key"]),
        sa.ForeignKeyConstraint(
            ["supplier_key"],
            ["core.dim_supplier.supplier_key"],
        ),
        sa.ForeignKeyConstraint(
            ["product_key"],
            ["core.dim_product.product_key"],
        ),
        sa.ForeignKeyConstraint(
            ["location_key"],
            ["core.dim_location.location_key"],
        ),
        sa.UniqueConstraint("purchase_id", "purchase_item_id"),
        sa.CheckConstraint("quantity > 0", name="quantity_positive"),
        sa.CheckConstraint("unit_cost >= 0", name="unit_cost_non_negative"),
        sa.CheckConstraint("item_discount >= 0", name="item_discount_non_negative"),
        sa.CheckConstraint("line_total >= 0", name="line_total_non_negative"),
        schema="core",
    )

    op.create_table(
        "fact_returns",
        sa.Column("return_key", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("return_id", sa.String(length=50), nullable=False, unique=True),
        sa.Column("date_key", sa.Integer(), nullable=False),
        sa.Column("return_type", sa.Text(), nullable=False),
        sa.Column("order_id", sa.String(length=50), nullable=True),
        sa.Column("purchase_id", sa.String(length=50), nullable=True),
        sa.Column("customer_key", sa.BigInteger(), nullable=True),
        sa.Column("location_key", sa.BigInteger(), nullable=False),
        sa.Column("cash_account_key", sa.BigInteger(), nullable=False),
        sa.Column("refund_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column(
            "due_adjustment",
            sa.Numeric(14, 2),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "cash_refund",
            sa.Numeric(14, 2),
            nullable=False,
            server_default="0",
        ),
        sa.Column("returned_by", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("source_created_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("source_system", sa.Text(), nullable=False),
        sa.Column("source_table", sa.Text(), nullable=False),
        sa.Column("source_row_identifier", sa.Text(), nullable=True),
        sa.Column("ingestion_batch_id", sa.UUID(), nullable=False),
        sa.Column(
            "ingested_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["date_key"], ["core.dim_date.date_key"]),
        sa.ForeignKeyConstraint(
            ["customer_key"],
            ["core.dim_customer.customer_key"],
        ),
        sa.ForeignKeyConstraint(
            ["location_key"],
            ["core.dim_location.location_key"],
        ),
        sa.ForeignKeyConstraint(
            ["cash_account_key"],
            ["core.dim_cash_account.cash_account_key"],
        ),
        sa.CheckConstraint("refund_amount >= 0", name="refund_amount_non_negative"),
        sa.CheckConstraint("due_adjustment >= 0", name="due_adjustment_non_negative"),
        sa.CheckConstraint("cash_refund >= 0", name="cash_refund_non_negative"),
        sa.CheckConstraint(
            """
            (
                return_type = 'CUSTOMER_RETURN'
                AND order_id IS NOT NULL
                AND purchase_id IS NULL
            )
            OR
            (
                return_type = 'SUPPLIER_RETURN'
                AND purchase_id IS NOT NULL
                AND order_id IS NULL
            )
            """,
            name="valid_return_type_and_reference",
        ),
        schema="core",
    )

    op.create_table(
        "fact_return_items",
        sa.Column(
            "return_item_key",
            sa.BigInteger(),
            sa.Identity(),
            primary_key=True,
        ),
        sa.Column(
            "return_item_id",
            sa.String(length=50),
            nullable=False,
            unique=True,
        ),
        sa.Column("return_id", sa.String(length=50), nullable=False),
        sa.Column("product_key", sa.BigInteger(), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=False),
        sa.Column("line_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column(
            "returned_cogs",
            sa.Numeric(14, 2),
            nullable=False,
            server_default="0",
        ),
        sa.Column("source_system", sa.Text(), nullable=False),
        sa.Column("source_table", sa.Text(), nullable=False),
        sa.Column("source_row_identifier", sa.Text(), nullable=True),
        sa.Column("ingestion_batch_id", sa.UUID(), nullable=False),
        sa.Column(
            "ingested_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["return_id"],
            ["core.fact_returns.return_id"],
        ),
        sa.ForeignKeyConstraint(
            ["product_key"],
            ["core.dim_product.product_key"],
        ),
        sa.CheckConstraint("quantity > 0", name="quantity_positive"),
        sa.CheckConstraint("unit_price >= 0", name="unit_price_non_negative"),
        sa.CheckConstraint("line_amount >= 0", name="line_amount_non_negative"),
        sa.CheckConstraint("returned_cogs >= 0", name="returned_cogs_non_negative"),
        schema="core",
    )

    op.create_table(
        "fact_stock_movements",
        sa.Column(
            "stock_movement_key",
            sa.BigInteger(),
            sa.Identity(),
            primary_key=True,
        ),
        sa.Column("movement_id", sa.String(length=50), nullable=False, unique=True),
        sa.Column("date_key", sa.Integer(), nullable=False),
        sa.Column("product_key", sa.BigInteger(), nullable=False),
        sa.Column("movement_type", sa.Text(), nullable=False),
        sa.Column("direction", sa.Text(), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("from_location_key", sa.BigInteger(), nullable=True),
        sa.Column("to_location_key", sa.BigInteger(), nullable=True),
        sa.Column("reference_id", sa.String(length=50), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("source_system", sa.Text(), nullable=False),
        sa.Column("source_table", sa.Text(), nullable=False),
        sa.Column("source_row_identifier", sa.Text(), nullable=True),
        sa.Column("ingestion_batch_id", sa.UUID(), nullable=False),
        sa.Column(
            "ingested_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["date_key"], ["core.dim_date.date_key"]),
        sa.ForeignKeyConstraint(
            ["product_key"],
            ["core.dim_product.product_key"],
        ),
        sa.ForeignKeyConstraint(
            ["from_location_key"],
            ["core.dim_location.location_key"],
        ),
        sa.ForeignKeyConstraint(
            ["to_location_key"],
            ["core.dim_location.location_key"],
        ),
        sa.CheckConstraint("quantity > 0", name="quantity_positive"),
        sa.CheckConstraint("direction IN ('IN', 'OUT')", name="valid_movement_direction"),
        schema="core",
    )

    op.create_table(
        "fact_cash_transactions",
        sa.Column(
            "cash_transaction_key",
            sa.BigInteger(),
            sa.Identity(),
            primary_key=True,
        ),
        sa.Column(
            "transaction_id",
            sa.String(length=50),
            nullable=False,
            unique=True,
        ),
        sa.Column("date_key", sa.Integer(), nullable=False),
        sa.Column("cash_account_key", sa.BigInteger(), nullable=False),
        sa.Column("transaction_type", sa.Text(), nullable=False),
        sa.Column("direction", sa.Text(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("reference_type", sa.Text(), nullable=True),
        sa.Column("reference_id", sa.String(length=50), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.Column("source_created_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("source_system", sa.Text(), nullable=False),
        sa.Column("source_table", sa.Text(), nullable=False),
        sa.Column("source_row_identifier", sa.Text(), nullable=True),
        sa.Column("ingestion_batch_id", sa.UUID(), nullable=False),
        sa.Column(
            "ingested_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["date_key"], ["core.dim_date.date_key"]),
        sa.ForeignKeyConstraint(
            ["cash_account_key"],
            ["core.dim_cash_account.cash_account_key"],
        ),
        sa.CheckConstraint("direction IN ('IN', 'OUT')", name="valid_movement_direction"),
        sa.CheckConstraint("amount > 0", name="amount_positive"),
        schema="core",
    )

    op.create_table(
        "fact_expenses",
        sa.Column("expense_key", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("expense_id", sa.String(length=50), nullable=False, unique=True),
        sa.Column("date_key", sa.Integer(), nullable=False),
        sa.Column("expense_category", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("payment_method", sa.Text(), nullable=False),
        sa.Column("cash_account_key", sa.BigInteger(), nullable=True),
        sa.Column("paid_by", sa.Text(), nullable=True),
        sa.Column("reference", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("source_system", sa.Text(), nullable=False),
        sa.Column("source_table", sa.Text(), nullable=False),
        sa.Column("source_row_identifier", sa.Text(), nullable=True),
        sa.Column("ingestion_batch_id", sa.UUID(), nullable=False),
        sa.Column(
            "ingested_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["date_key"], ["core.dim_date.date_key"]),
        sa.ForeignKeyConstraint(
            ["cash_account_key"],
            ["core.dim_cash_account.cash_account_key"],
        ),
        sa.CheckConstraint("amount > 0", name="amount_positive"),
        schema="core",
    )

    op.create_table(
        "fact_partner_capital",
        sa.Column("capital_key", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "capital_transaction_id",
            sa.String(length=50),
            nullable=False,
            unique=True,
        ),
        sa.Column("date_key", sa.Integer(), nullable=False),
        sa.Column("partner_key", sa.BigInteger(), nullable=False),
        sa.Column("cash_account_key", sa.BigInteger(), nullable=False),
        sa.Column("transaction_type", sa.Text(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("reference_id", sa.String(length=50), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("source_system", sa.Text(), nullable=False),
        sa.Column("source_table", sa.Text(), nullable=False),
        sa.Column("source_row_identifier", sa.Text(), nullable=True),
        sa.Column("ingestion_batch_id", sa.UUID(), nullable=False),
        sa.Column(
            "ingested_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["date_key"], ["core.dim_date.date_key"]),
        sa.ForeignKeyConstraint(
            ["partner_key"],
            ["core.dim_partner.partner_key"],
        ),
        sa.ForeignKeyConstraint(
            ["cash_account_key"],
            ["core.dim_cash_account.cash_account_key"],
        ),
        sa.CheckConstraint("amount > 0", name="amount_positive"),
        schema="core",
    )


def downgrade() -> None:
    # Drop fact tables first because they depend on dimensions.
    op.drop_table("fact_partner_capital", schema="core")
    op.drop_table("fact_expenses", schema="core")
    op.drop_table("fact_cash_transactions", schema="core")
    op.drop_table("fact_stock_movements", schema="core")
    op.drop_table("fact_return_items", schema="core")
    op.drop_table("fact_returns", schema="core")
    op.drop_table("fact_purchases", schema="core")
    op.drop_table("fact_payments", schema="core")
    op.drop_table("fact_sales", schema="core")
    op.drop_table("fact_orders", schema="core")

    # Drop dimensions in dependency order.
    op.drop_table("dim_cash_account", schema="core")
    op.drop_table("dim_location", schema="core")
    op.drop_table("dim_supplier", schema="core")
    op.drop_table("dim_product", schema="core")
    op.drop_table("dim_customer", schema="core")
    op.drop_table("dim_partner", schema="core")
    op.drop_table("dim_date", schema="core")