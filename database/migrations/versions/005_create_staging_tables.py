"""create staging tables

Revision ID: 005_staging_tables
Revises: 004_raw_transaction
Create Date: 2026-08-18

Create normalized staging tables for HBMS source data.

The staging layer sits between raw source storage and the canonical core
analytical model:

    raw -> staging -> core -> analytics

Staging records are normalized and validated before core loading while
preserving complete source lineage.

Revision history:
    001_create_schemas
        -> 002_create_ingestion_metadata
        -> 003_raw_reference
        -> 004_raw_transaction
        -> 005_staging_tables
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "005_staging_tables"
down_revision: Union[str, None] = "004_raw_transaction"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------
# Common lineage columns
# ---------------------------------------------------------------------
#
# Every staging record must remain traceable to its original source row.
#
# POSTGRESQL_SCHEMA.md requires:
#   - source_system
#   - source_table
#   - source_row_identifier
#   - ingestion_batch_id
#   - ingested_at
#
# Additional staging-specific fields support validation and loading.
#

LINEAGE_COLUMNS = """
    source_system           TEXT NOT NULL,
    source_table            TEXT NOT NULL,
    source_row_identifier   TEXT NOT NULL,
    ingestion_batch_id      UUID NOT NULL
        REFERENCES raw.ingestion_batches(ingestion_batch_id),
    ingested_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    source_hash             TEXT,
    record_status           TEXT NOT NULL DEFAULT 'pending',
    validation_error        TEXT
"""


def upgrade() -> None:
    # ================================================================
    # Reference / master data
    # ================================================================

    op.execute(
        f"""
        CREATE TABLE staging.stg_products (
            stg_product_id       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

            product_id           VARCHAR(50) NOT NULL,
            product_name         TEXT NOT NULL,
            category             TEXT,
            unit                 TEXT,
            selling_price        NUMERIC(14,2),
            cost_price           NUMERIC(14,2),
            opening_stock        NUMERIC(14,3),
            reorder_level        NUMERIC(14,3),
            active               BOOLEAN,

            {LINEAGE_COLUMNS},

            UNIQUE (
                ingestion_batch_id,
                source_table,
                source_row_identifier
            )
        )
        """
    )

    op.execute(
        f"""
        CREATE TABLE staging.stg_customers (
            stg_customer_id      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

            customer_id          VARCHAR(50) NOT NULL,
            customer_name        TEXT NOT NULL,
            contact              TEXT,
            address              TEXT,
            first_order_date     DATE,
            last_order_date      DATE,
            total_orders         INTEGER,
            total_spent          NUMERIC(14,2),
            total_paid           NUMERIC(14,2),
            total_due            NUMERIC(14,2),

            {LINEAGE_COLUMNS},

            UNIQUE (
                ingestion_batch_id,
                source_table,
                source_row_identifier
            )
        )
        """
    )

    op.execute(
        f"""
        CREATE TABLE staging.stg_partners (
            stg_partner_id       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

            partner_id           VARCHAR(50) NOT NULL,
            partner_name         TEXT NOT NULL,
            active               BOOLEAN,

            {LINEAGE_COLUMNS},

            UNIQUE (
                ingestion_batch_id,
                source_table,
                source_row_identifier
            )
        )
        """
    )

    op.execute(
        f"""
        CREATE TABLE staging.stg_suppliers (
            stg_supplier_id      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

            supplier_id          VARCHAR(50) NOT NULL,
            supplier_name        TEXT NOT NULL,
            contact              TEXT,
            address              TEXT,
            active               BOOLEAN,

            {LINEAGE_COLUMNS},

            UNIQUE (
                ingestion_batch_id,
                source_table,
                source_row_identifier
            )
        )
        """
    )

    op.execute(
        f"""
        CREATE TABLE staging.stg_stock_locations (
            stg_stock_location_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

            stock_location_id     VARCHAR(50) NOT NULL,
            location_name         TEXT NOT NULL,
            location_type         TEXT,
            partner_id            VARCHAR(50),
            active                BOOLEAN,

            {LINEAGE_COLUMNS},

            UNIQUE (
                ingestion_batch_id,
                source_table,
                source_row_identifier
            )
        )
        """
    )

    op.execute(
        f"""
        CREATE TABLE staging.stg_cash_accounts (
            stg_cash_account_id  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

            cash_account_id      VARCHAR(50) NOT NULL,
            account_name         TEXT NOT NULL,
            account_type         TEXT,
            owner_id             VARCHAR(50),
            active               BOOLEAN,

            total_in             NUMERIC(14,2),
            total_out            NUMERIC(14,2),
            current_balance      NUMERIC(14,2),

            {LINEAGE_COLUMNS},

            UNIQUE (
                ingestion_batch_id,
                source_table,
                source_row_identifier
            )
        )
        """
    )

    # ================================================================
    # Orders and payments
    # ================================================================

    op.execute(
        f"""
        CREATE TABLE staging.stg_orders (
            stg_order_id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

            order_id             VARCHAR(50) NOT NULL,
            order_date           DATE NOT NULL,
            customer_id          VARCHAR(50),

            subtotal             NUMERIC(14,2),
            discount             NUMERIC(14,2),
            delivery_charge      NUMERIC(14,2),
            total_amount         NUMERIC(14,2),
            paid_amount          NUMERIC(14,2),
            due_amount           NUMERIC(14,2),
            order_status         TEXT,

            {LINEAGE_COLUMNS},

            UNIQUE (
                ingestion_batch_id,
                source_table,
                source_row_identifier
            )
        )
        """
    )

    op.execute(
        f"""
        CREATE TABLE staging.stg_order_items (
            stg_order_item_id    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

            order_item_id        VARCHAR(50) NOT NULL,
            order_id             VARCHAR(50) NOT NULL,
            product_id           VARCHAR(50) NOT NULL,
            stock_location_id    VARCHAR(50),

            quantity             NUMERIC(14,3) NOT NULL,
            unit_price           NUMERIC(14,2),
            cost_price           NUMERIC(14,2),
            line_amount          NUMERIC(14,2),

            {LINEAGE_COLUMNS},

            UNIQUE (
                ingestion_batch_id,
                source_table,
                source_row_identifier
            )
        )
        """
    )

    op.execute(
        f"""
        CREATE TABLE staging.stg_payments (
            stg_payment_id       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

            payment_id           VARCHAR(50) NOT NULL,
            payment_date         DATE NOT NULL,
            customer_id          VARCHAR(50),
            order_id             VARCHAR(50),

            amount               NUMERIC(14,2) NOT NULL,
            payment_method       TEXT,
            collected_by         VARCHAR(50),
            cash_account_id      VARCHAR(50),
            notes                TEXT,

            {LINEAGE_COLUMNS},

            UNIQUE (
                ingestion_batch_id,
                source_table,
                source_row_identifier
            )
        )
        """
    )

    # ================================================================
    # Purchases
    # ================================================================

    op.execute(
        f"""
        CREATE TABLE staging.stg_purchases (
            stg_purchase_id      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

            purchase_id          VARCHAR(50) NOT NULL,
            purchase_date        DATE NOT NULL,
            supplier_id          VARCHAR(50),

            total_amount         NUMERIC(14,2),
            paid_amount          NUMERIC(14,2),
            due_amount           NUMERIC(14,2),
            purchase_status      TEXT,

            {LINEAGE_COLUMNS},

            UNIQUE (
                ingestion_batch_id,
                source_table,
                source_row_identifier
            )
        )
        """
    )

    op.execute(
        f"""
        CREATE TABLE staging.stg_purchase_items (
            stg_purchase_item_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

            purchase_item_id     VARCHAR(50) NOT NULL,
            purchase_id          VARCHAR(50) NOT NULL,
            product_id           VARCHAR(50) NOT NULL,
            stock_location_id    VARCHAR(50),

            quantity             NUMERIC(14,3) NOT NULL,
            unit_cost            NUMERIC(14,2),
            line_amount          NUMERIC(14,2),

            {LINEAGE_COLUMNS},

            UNIQUE (
                ingestion_batch_id,
                source_table,
                source_row_identifier
            )
        )
        """
    )

    # ================================================================
    # Customer returns
    # ================================================================

    op.execute(
        f"""
        CREATE TABLE staging.stg_returns (
            stg_return_id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

            return_id            VARCHAR(50) NOT NULL,
            return_date          DATE NOT NULL,
            customer_id          VARCHAR(50),
            order_id             VARCHAR(50),

            total_amount         NUMERIC(14,2),
            refund_amount        NUMERIC(14,2),
            adjustment_amount    NUMERIC(14,2),
            return_status        TEXT,
            notes                TEXT,

            {LINEAGE_COLUMNS},

            UNIQUE (
                ingestion_batch_id,
                source_table,
                source_row_identifier
            )
        )
        """
    )

    op.execute(
        f"""
        CREATE TABLE staging.stg_return_items (
            stg_return_item_id   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

            return_item_id       VARCHAR(50) NOT NULL,
            return_id            VARCHAR(50) NOT NULL,
            order_item_id        VARCHAR(50),
            product_id           VARCHAR(50) NOT NULL,

            quantity             NUMERIC(14,3) NOT NULL,
            unit_price           NUMERIC(14,2),
            amount               NUMERIC(14,2),

            {LINEAGE_COLUMNS},

            UNIQUE (
                ingestion_batch_id,
                source_table,
                source_row_identifier
            )
        )
        """
    )

    # ================================================================
    # Inventory movements
    # ================================================================

    op.execute(
        f"""
        CREATE TABLE staging.stg_stock_movements (
            stg_stock_movement_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

            movement_id           VARCHAR(50) NOT NULL,
            movement_date         DATE NOT NULL,
            product_id            VARCHAR(50) NOT NULL,

            from_location_id      VARCHAR(50),
            to_location_id        VARCHAR(50),
            movement_type         TEXT NOT NULL,
            quantity              NUMERIC(14,3) NOT NULL,
            reference_id          VARCHAR(50),
            notes                 TEXT,

            {LINEAGE_COLUMNS},

            UNIQUE (
                ingestion_batch_id,
                source_table,
                source_row_identifier
            )
        )
        """
    )

    # ================================================================
    # Cash transactions
    # ================================================================

    op.execute(
        f"""
        CREATE TABLE staging.stg_cash_transactions (
            stg_cash_transaction_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

            transaction_id          VARCHAR(50) NOT NULL,
            transaction_date        DATE NOT NULL,

            cash_account_id         VARCHAR(50),
            transaction_type        TEXT NOT NULL,
            amount                  NUMERIC(14,2) NOT NULL,

            related_partner_id      VARCHAR(50),
            reference_id            VARCHAR(50),
            notes                   TEXT,

            {LINEAGE_COLUMNS},

            UNIQUE (
                ingestion_batch_id,
                source_table,
                source_row_identifier
            )
        )
        """
    )

    # ================================================================
    # Expenses
    # ================================================================

    op.execute(
        f"""
        CREATE TABLE staging.stg_expenses (
            stg_expense_id       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

            expense_id           VARCHAR(50) NOT NULL,
            expense_date         DATE NOT NULL,

            expense_category     TEXT,
            description          TEXT,
            amount               NUMERIC(14,2) NOT NULL,

            paid_by_partner_id   VARCHAR(50),
            cash_account_id      VARCHAR(50),
            reference_id         VARCHAR(50),

            {LINEAGE_COLUMNS},

            UNIQUE (
                ingestion_batch_id,
                source_table,
                source_row_identifier
            )
        )
        """
    )

    # ================================================================
    # Partner capital
    # ================================================================

    op.execute(
        f"""
        CREATE TABLE staging.stg_partner_capital (
            stg_partner_capital_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

            partner_capital_entry_id VARCHAR(50) NOT NULL,
            entry_date               DATE NOT NULL,
            partner_id               VARCHAR(50) NOT NULL,

            transaction_type         TEXT NOT NULL,
            amount                   NUMERIC(14,2) NOT NULL,
            cash_account_id          VARCHAR(50),
            notes                    TEXT,

            {LINEAGE_COLUMNS},

            UNIQUE (
                ingestion_batch_id,
                source_table,
                source_row_identifier
            )
        )
        """
    )

    # ================================================================
    # Indexes for common staging operations
    # ================================================================

    tables_with_status = (
        "stg_products",
        "stg_customers",
        "stg_partners",
        "stg_suppliers",
        "stg_stock_locations",
        "stg_cash_accounts",
        "stg_orders",
        "stg_order_items",
        "stg_payments",
        "stg_purchases",
        "stg_purchase_items",
        "stg_returns",
        "stg_return_items",
        "stg_stock_movements",
        "stg_cash_transactions",
        "stg_expenses",
        "stg_partner_capital",
    )

    for table in tables_with_status:
        op.execute(
            f"""
            CREATE INDEX ix_{table}_status
            ON staging.{table} (record_status)
            """
        )

        op.execute(
            f"""
            CREATE INDEX ix_{table}_batch
            ON staging.{table} (ingestion_batch_id)
            """
        )


def downgrade() -> None:
    tables = (
        "stg_partner_capital",
        "stg_expenses",
        "stg_cash_transactions",
        "stg_stock_movements",
        "stg_return_items",
        "stg_returns",
        "stg_purchase_items",
        "stg_purchases",
        "stg_payments",
        "stg_order_items",
        "stg_orders",
        "stg_cash_accounts",
        "stg_stock_locations",
        "stg_suppliers",
        "stg_partners",
        "stg_customers",
        "stg_products",
    )

    for table in tables:
        op.execute(f"DROP TABLE IF EXISTS staging.{table}")