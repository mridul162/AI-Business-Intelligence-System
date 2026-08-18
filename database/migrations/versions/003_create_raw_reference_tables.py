"""
create raw reference tables

Revision ID: 003_create_raw_reference_tables
Revises: 002_create_ingestion_metadata
Create Date: 2026-08-18

Creates the source-oriented raw reference-data tables used to ingest
HBMS master/reference sheets before transformation into staging and
core analytical models.

Tables:
    raw.customers
    raw.products
    raw.partners
    raw.cash_accounts
    raw.stock_locations
    raw.lists

Raw-layer design:
    - Source business values are preserved primarily as TEXT.
    - No business-level foreign keys are enforced between raw tables.
    - Each record is linked to an ingestion batch.
    - Source row number and row hash support lineage, change detection,
      replay, and troubleshooting.

The raw layer intentionally preserves source representation. Type
conversion, normalization, enum validation, and referential validation
belong to the staging layer.

HBMS source structures reflected here include:
    Products:
        Product_ID, Product_Name, Category, Unit, Selling_Price,
        Cost_Price, Opening_Stock, Reorder_Level, Active.

    Partners:
        Partner_ID, Partner_Name, Role, Active.

    Cash_Accounts:
        Cash_Account_ID, Account_Name, Account_Type, Owner_ID, Active.

    Stock_Locations:
        Stock_Location_ID, Location_Name, Location_Type, Partner_ID,
        Active.

    Customers:
        Customer_ID, Customer_Name, Contact, Address,
        First_Order_Date, Last_Order_Date, Total_Orders, Total_Spent,
        Total_Paid, Total_Due, Status.

    Lists:
        Source-managed list/reference values.

Source columns are deliberately not converted into analytical types in
this migration. Raw data must remain as close as practical to the
operational source for auditability and reproducibility.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# Alembic revision identifiers.
revision: str = "003_create_raw_reference_tables"
down_revision: Union[str, None] = "002_create_ingestion_metadata"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _raw_lineage_columns() -> list[sa.Column]:
    """Return the standard lineage columns shared by raw source tables."""
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
    """Create standard ingestion/lineage indexes for a raw table."""
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
    """Drop standard ingestion/lineage indexes for a raw table."""
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
    # 1. CUSTOMERS
    # ==========================================================
    #
    # Actual source structure:
    #
    # Customer_ID
    # Customer_Name
    # Contact
    # Address
    # First_Order_Date
    # Last_Order_Date
    # Total_Orders
    # Total_Spent
    # Total_Paid
    # Total_Due
    # Status
    #
    op.create_table(
        "customers",
        *_raw_lineage_columns(),
        sa.Column("customer_id", sa.Text(), nullable=True),
        sa.Column("customer_name", sa.Text(), nullable=True),
        sa.Column("contact", sa.Text(), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("first_order_date", sa.Text(), nullable=True),
        sa.Column("last_order_date", sa.Text(), nullable=True),
        sa.Column("total_orders", sa.Text(), nullable=True),
        sa.Column("total_spent", sa.Text(), nullable=True),
        sa.Column("total_paid", sa.Text(), nullable=True),
        sa.Column("total_due", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=True),
        *_raw_lineage_constraints("customers"),
        schema="raw",
    )

    _create_raw_lineage_indexes("customers")

    op.create_index(
        "ix_customers_customer_id",
        "customers",
        ["customer_id"],
        schema="raw",
    )

    op.create_index(
        "ix_customers_contact",
        "customers",
        ["contact"],
        schema="raw",
    )

    # ==========================================================
    # 2. PRODUCTS
    # ==========================================================
    #
    # Actual active source structure uses the first nine columns:
    #
    # Product_ID
    # Product_Name
    # Category
    # Unit
    # Selling_Price
    # Cost_Price
    # Opening_Stock
    # Reorder_Level
    # Active
    #
    op.create_table(
        "products",
        *_raw_lineage_columns(),
        sa.Column("product_id", sa.Text(), nullable=True),
        sa.Column("product_name", sa.Text(), nullable=True),
        sa.Column("category", sa.Text(), nullable=True),
        sa.Column("unit", sa.Text(), nullable=True),
        sa.Column("selling_price", sa.Text(), nullable=True),
        sa.Column("cost_price", sa.Text(), nullable=True),
        sa.Column("opening_stock", sa.Text(), nullable=True),
        sa.Column("reorder_level", sa.Text(), nullable=True),
        sa.Column("active", sa.Text(), nullable=True),
        *_raw_lineage_constraints("products"),
        schema="raw",
    )

    _create_raw_lineage_indexes("products")

    op.create_index(
        "ix_products_product_id",
        "products",
        ["product_id"],
        schema="raw",
    )

    # ==========================================================
    # 3. PARTNERS
    # ==========================================================
    #
    # Partner_ID
    # Partner_Name
    # Role
    # Active
    #
    op.create_table(
        "partners",
        *_raw_lineage_columns(),
        sa.Column("partner_id", sa.Text(), nullable=True),
        sa.Column("partner_name", sa.Text(), nullable=True),
        sa.Column("role", sa.Text(), nullable=True),
        sa.Column("active", sa.Text(), nullable=True),
        *_raw_lineage_constraints("partners"),
        schema="raw",
    )

    _create_raw_lineage_indexes("partners")

    op.create_index(
        "ix_partners_partner_id",
        "partners",
        ["partner_id"],
        schema="raw",
    )

    # ==========================================================
    # 4. CASH ACCOUNTS
    # ==========================================================
    #
    # Cash_Account_ID
    # Account_Name
    # Account_Type
    # Owner_ID
    # Active
    #
    op.create_table(
        "cash_accounts",
        *_raw_lineage_columns(),
        sa.Column("cash_account_id", sa.Text(), nullable=True),
        sa.Column("account_name", sa.Text(), nullable=True),
        sa.Column("account_type", sa.Text(), nullable=True),
        sa.Column("owner_id", sa.Text(), nullable=True),
        sa.Column("active", sa.Text(), nullable=True),
        *_raw_lineage_constraints("cash_accounts"),
        schema="raw",
    )

    _create_raw_lineage_indexes("cash_accounts")

    op.create_index(
        "ix_cash_accounts_cash_account_id",
        "cash_accounts",
        ["cash_account_id"],
        schema="raw",
    )

    # ==========================================================
    # 5. STOCK LOCATIONS
    # ==========================================================
    #
    # Stock_Location_ID
    # Location_Name
    # Location_Type
    # Partner_ID
    # Active
    #
    op.create_table(
        "stock_locations",
        *_raw_lineage_columns(),
        sa.Column("stock_location_id", sa.Text(), nullable=True),
        sa.Column("location_name", sa.Text(), nullable=True),
        sa.Column("location_type", sa.Text(), nullable=True),
        sa.Column("partner_id", sa.Text(), nullable=True),
        sa.Column("active", sa.Text(), nullable=True),
        *_raw_lineage_constraints("stock_locations"),
        schema="raw",
    )

    _create_raw_lineage_indexes("stock_locations")

    op.create_index(
        "ix_stock_locations_stock_location_id",
        "stock_locations",
        ["stock_location_id"],
        schema="raw",
    )

    # ==========================================================
    # 6. LISTS
    # ==========================================================
    #
    # Lists is a source-managed reference sheet containing values for
    # operational enums/dropdowns such as order status, payment method,
    # transaction type, movement type, expense category, and purchase
    # status.
    #
    # The exact list layout is preserved generically rather than imposing
    # business enum CHECK constraints at the raw layer.
    #
    op.create_table(
        "lists",
        *_raw_lineage_columns(),
        sa.Column("list_name", sa.Text(), nullable=True),
        sa.Column("list_value", sa.Text(), nullable=True),
        *_raw_lineage_constraints("lists"),
        schema="raw",
    )

    _create_raw_lineage_indexes("lists")

    op.create_index(
        "ix_lists_list_name",
        "lists",
        ["list_name"],
        schema="raw",
    )


def downgrade() -> None:
    # Reverse dependency/order is not critical among these tables because
    # they do not have business foreign keys to one another.

    # ==========================================================
    # 1. LISTS
    # ==========================================================
    op.drop_index(
        "ix_lists_list_name",
        table_name="lists",
        schema="raw",
    )
    _drop_raw_lineage_indexes("lists")
    op.drop_table("lists", schema="raw")

    # ==========================================================
    # 2. STOCK LOCATIONS
    # ==========================================================
    op.drop_index(
        "ix_stock_locations_stock_location_id",
        table_name="stock_locations",
        schema="raw",
    )
    _drop_raw_lineage_indexes("stock_locations")
    op.drop_table("stock_locations", schema="raw")

    # ==========================================================
    # 3. CASH ACCOUNTS
    # ==========================================================
    op.drop_index(
        "ix_cash_accounts_cash_account_id",
        table_name="cash_accounts",
        schema="raw",
    )
    _drop_raw_lineage_indexes("cash_accounts")
    op.drop_table("cash_accounts", schema="raw")

    # ==========================================================
    # 4. PARTNERS
    # ==========================================================
    op.drop_index(
        "ix_partners_partner_id",
        table_name="partners",
        schema="raw",
    )
    _drop_raw_lineage_indexes("partners")
    op.drop_table("partners", schema="raw")

    # ==========================================================
    # 5. PRODUCTS
    # ==========================================================
    op.drop_index(
        "ix_products_product_id",
        table_name="products",
        schema="raw",
    )
    _drop_raw_lineage_indexes("products")
    op.drop_table("products", schema="raw")

    # ==========================================================
    # 6. CUSTOMERS
    # ==========================================================
    op.drop_index(
        "ix_customers_contact",
        table_name="customers",
        schema="raw",
    )
    op.drop_index(
        "ix_customers_customer_id",
        table_name="customers",
        schema="raw",
    )
    _drop_raw_lineage_indexes("customers")
    op.drop_table("customers", schema="raw")