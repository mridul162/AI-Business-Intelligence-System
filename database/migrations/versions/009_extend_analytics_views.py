"""Extend analytics views for BI and AI reporting.

Revision ID: 009_extend_analytics_views
Revises: 008_reconcile_pipeline_mappings
Create Date: 2026-08-22

Extends the analytics layer without modifying historical migrations.

Changes:
    - Replaces the ambiguous order-level analytics.v_sales view with
      analytics.v_orders.
    - Creates a true sales-line analytics.v_sales view from
      core.fact_sales.
    - Adds analytics views for:
        * return items
        * cash transactions
        * expenses
        * partner capital
        * stock movements
    - Rebuilds the daily business summary using the expanded warehouse
      model.

The core schema remains the canonical analytical storage layer.
The analytics schema provides denormalized, reporting-friendly views
for BI dashboards and the AI analytics layer.

NOTE (revision review, 2026-08-22):
    analytics.v_orders and the `orders` CTE in
    analytics.v_daily_business_summary reference core.fact_orders.
    That table's schema was not available during this review, so those
    two blocks are carried over UNVERIFIED from the original draft.
    Every other view in this file has been checked column-by-column
    against \\d output for its source fact table and corrected where
    the original draft referenced columns that don't exist:

      * analytics.v_sales            -> core.fact_sales
      * analytics.v_return_items     -> core.fact_return_items
      * analytics.v_cash_transactions-> core.fact_cash_transactions
      * analytics.v_expenses         -> core.fact_expenses
      * analytics.v_partner_capital  -> core.fact_partner_capital
      * analytics.v_stock_movements  -> core.fact_stock_movements

    See inline comments at each fix for details.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "009_extend_analytics_views"
down_revision: Union[str, None] = "008_reconcile_pipeline_mappings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ==========================================================
    # 1. Replace legacy order-level v_sales
    # ==========================================================
    #
    # In revision 007, analytics.v_sales was built from fact_orders.
    # That makes the name misleading because fact_orders is an
    # order-header fact, not a sales-line fact.
    #
    # Preserve the semantic distinction:
    #
    #   analytics.v_orders -> order-level analysis
    #   analytics.v_sales  -> sales-line/product-level analysis
    #
    # ==========================================================

    op.execute("DROP VIEW IF EXISTS analytics.v_daily_business_summary")
    op.execute("DROP VIEW IF EXISTS analytics.v_sales")

    # ==========================================================
    # 2. Order-level analytics
    # ==========================================================
    #
    # UNVERIFIED: core.fact_orders schema was not available for this
    # review. Columns below (order_key, order_id, customer_key,
    # subtotal, invoice_discount, delivery_charge, total_amount,
    # order_status, collected_by, source_created_at, source_system,
    # source_table, source_row_identifier, ingestion_batch_id,
    # ingested_at) are carried over from the original draft as-is.
    # Confirm against `\d core.fact_orders` before applying.
    # ==========================================================

    op.execute(
        """
        CREATE VIEW analytics.v_orders AS
        SELECT
            o.order_key,
            o.order_id,

            d.date_key,
            d.date AS order_date,
            d.year,
            d.quarter,
            d.month,
            d.month_name,
            d.week,
            d.day,
            d.day_name,
            d.is_weekend,

            c.customer_key,
            c.customer_id,
            c.customer_name,
            c.phone AS customer_phone,
            c.address AS customer_address,
            c.status AS customer_status,

            o.subtotal,
            o.invoice_discount,
            o.delivery_charge,
            o.total_amount,

            (
                o.subtotal
                - o.invoice_discount
                + o.delivery_charge
            ) AS calculated_order_amount,

            o.order_status,
            o.collected_by,

            o.source_created_at,
            o.source_system,
            o.source_table,
            o.source_row_identifier,
            o.ingestion_batch_id,
            o.ingested_at

        FROM core.fact_orders AS o

        JOIN core.dim_date AS d
            ON o.date_key = d.date_key

        LEFT JOIN core.dim_customer AS c
            ON o.customer_key = c.customer_key;
        """
    )

    # ==========================================================
    # 3. Sales-line analytics
    # ==========================================================
    #
    # FIXED vs. original draft (core.fact_sales columns are:
    # sales_key, order_id, order_item_id, date_key, customer_key,
    # product_key, location_key, quantity, unit_price, item_discount,
    # line_total, gross_sales, unit_cost, cogs, source_system, ...):
    #   - s.sale_key      -> s.sales_key       (no `sale_key` column)
    #   - s.sale_item_id  -> s.order_item_id   (no `sale_item_id` column)
    #   - exposed s.unit_cost, s.cogs, s.gross_sales directly instead
    #     of only recomputing a gross amount, since the warehouse
    #     already carries margin data on this fact table.
    # ==========================================================

    op.execute(
        """
        CREATE VIEW analytics.v_sales AS
        SELECT
            s.sales_key,
            s.order_item_id,
            s.order_id,

            d.date_key,
            d.date AS sale_date,
            d.year,
            d.quarter,
            d.month,
            d.month_name,
            d.week,
            d.day,
            d.day_name,
            d.is_weekend,

            c.customer_key,
            c.customer_id,
            c.customer_name,
            c.phone AS customer_phone,
            c.status AS customer_status,

            p.product_key,
            p.product_id,
            p.product_name,
            p.category AS product_category,
            p.unit AS product_unit,

            l.location_key,
            l.stock_location_id AS location_id,
            l.location_name,
            l.location_type,

            s.quantity,
            s.unit_price,
            s.item_discount,
            s.line_total,
            s.gross_sales,
            s.unit_cost,
            s.cogs,

            (
                s.quantity * s.unit_price
                - s.item_discount
            ) AS calculated_net_line_amount,

            s.source_system,
            s.source_table,
            s.source_row_identifier,
            s.ingestion_batch_id,
            s.ingested_at

        FROM core.fact_sales AS s

        JOIN core.dim_date AS d
            ON s.date_key = d.date_key

        LEFT JOIN core.dim_customer AS c
            ON s.customer_key = c.customer_key

        JOIN core.dim_product AS p
            ON s.product_key = p.product_key

        JOIN core.dim_location AS l
            ON s.location_key = l.location_key;
        """
    )

    # ==========================================================
    # 4. Payment analytics
    # ==========================================================
    # Verified against core.fact_payments - no changes needed.
    # cash_account_key and customer_key are both nullable on
    # fact_payments, so LEFT JOIN is correct for both.
    # ==========================================================

    op.execute("DROP VIEW IF EXISTS analytics.v_payments")

    op.execute(
        """
        CREATE VIEW analytics.v_payments AS
        SELECT
            p.payment_key,
            p.payment_id,

            d.date_key,
            d.date AS payment_date,
            d.year,
            d.quarter,
            d.month,
            d.month_name,

            p.order_id,

            c.customer_key,
            c.customer_id,
            c.customer_name,

            ca.cash_account_key,
            ca.cash_account_id,
            ca.account_name AS cash_account_name,
            ca.account_type AS cash_account_type,
            ca.owner_id AS cash_account_owner_id,

            p.amount,
            p.payment_method,
            p.collected_by,
            p.notes,

            p.source_created_at,
            p.source_system,
            p.source_table,
            p.source_row_identifier,
            p.ingestion_batch_id,
            p.ingested_at

        FROM core.fact_payments AS p

        JOIN core.dim_date AS d
            ON p.date_key = d.date_key

        LEFT JOIN core.dim_customer AS c
            ON p.customer_key = c.customer_key

        LEFT JOIN core.dim_cash_account AS ca
            ON p.cash_account_key = ca.cash_account_key;
        """
    )

    # ==========================================================
    # 5. Return analytics
    # ==========================================================
    # Verified against core.fact_returns - no changes needed.
    # location_key and cash_account_key are both NOT NULL on
    # fact_returns, so inner JOIN is correct for both; customer_key
    # is nullable, so LEFT JOIN is correct.
    # ==========================================================

    op.execute("DROP VIEW IF EXISTS analytics.v_returns")

    op.execute(
        """
        CREATE VIEW analytics.v_returns AS
        SELECT
            r.return_key,
            r.return_id,

            d.date_key,
            d.date AS return_date,
            d.year,
            d.quarter,
            d.month,
            d.month_name,

            r.return_type,
            r.order_id,
            r.purchase_id,

            c.customer_key,
            c.customer_id,
            c.customer_name,

            l.location_key,
            l.stock_location_id AS location_id,
            l.location_name,
            l.location_type,

            ca.cash_account_key,
            ca.cash_account_id,
            ca.account_name AS cash_account_name,
            ca.account_type AS cash_account_type,

            r.refund_amount,
            r.due_adjustment,
            r.cash_refund,

            r.returned_by,
            r.reason,
            r.status,
            r.notes,

            r.source_created_at,
            r.source_system,
            r.source_table,
            r.source_row_identifier,
            r.ingestion_batch_id,
            r.ingested_at

        FROM core.fact_returns AS r

        JOIN core.dim_date AS d
            ON r.date_key = d.date_key

        LEFT JOIN core.dim_customer AS c
            ON r.customer_key = c.customer_key

        JOIN core.dim_location AS l
            ON r.location_key = l.location_key

        JOIN core.dim_cash_account AS ca
            ON r.cash_account_key = ca.cash_account_key;
        """
    )

    # ==========================================================
    # 6. Return-item analytics
    # ==========================================================
    #
    # FIXED vs. original draft (core.fact_return_items columns are:
    # return_item_key, return_item_id, return_id, product_key,
    # quantity, unit_price, line_amount, returned_cogs,
    # source_system, ...; it has NO location_key and NO date_key):
    #   - ri.line_total -> ri.line_amount   (no `line_total` column)
    #   - added ri.returned_cogs (exists, useful for return margin)
    #   - dim_location join changed from ri.location_key (column does
    #     not exist on fact_return_items) to r.location_key, using
    #     the location recorded on the parent fact_returns row.
    # ==========================================================

    op.execute(
        """
        CREATE VIEW analytics.v_return_items AS
        SELECT
            ri.return_item_key,
            ri.return_item_id,
            ri.return_id,

            d.date_key,
            d.date AS return_date,
            d.year,
            d.quarter,
            d.month,
            d.month_name,

            r.return_type,
            r.order_id,
            r.purchase_id,
            r.status AS return_status,

            c.customer_key,
            c.customer_id,
            c.customer_name,

            p.product_key,
            p.product_id,
            p.product_name,
            p.category AS product_category,
            p.unit AS product_unit,

            l.location_key,
            l.stock_location_id AS location_id,
            l.location_name,

            ri.quantity,
            ri.unit_price,
            ri.line_amount,
            ri.returned_cogs,

            ri.source_system,
            ri.source_table,
            ri.source_row_identifier,
            ri.ingestion_batch_id,
            ri.ingested_at

        FROM core.fact_return_items AS ri

        JOIN core.fact_returns AS r
            ON ri.return_id = r.return_id

        JOIN core.dim_date AS d
            ON r.date_key = d.date_key

        LEFT JOIN core.dim_customer AS c
            ON r.customer_key = c.customer_key

        JOIN core.dim_product AS p
            ON ri.product_key = p.product_key

        JOIN core.dim_location AS l
            ON r.location_key = l.location_key;
        """
    )

    # ==========================================================
    # 7. Purchase analytics
    # ==========================================================
    # Verified against core.fact_purchases - no changes needed.
    # supplier_key, product_key and location_key are all NOT NULL
    # on fact_purchases, so inner JOIN is correct throughout.
    # ==========================================================

    op.execute("DROP VIEW IF EXISTS analytics.v_purchases")

    op.execute(
        """
        CREATE VIEW analytics.v_purchases AS
        SELECT
            p.purchase_key,
            p.purchase_id,
            p.purchase_item_id,

            d.date_key,
            d.date AS purchase_date,
            d.year,
            d.quarter,
            d.month,
            d.month_name,

            s.supplier_key,
            s.supplier_id,
            s.supplier_name,
            s.contact AS supplier_contact,
            s.address AS supplier_address,

            pr.product_key,
            pr.product_id,
            pr.product_name,
            pr.category AS product_category,
            pr.unit AS product_unit,

            l.location_key,
            l.stock_location_id AS location_id,
            l.location_name,
            l.location_type,

            p.quantity,
            p.unit_cost,
            p.item_discount,
            p.line_total,

            (
                p.quantity * p.unit_cost
            ) AS gross_purchase_amount,

            (
                p.quantity * p.unit_cost
                - p.item_discount
            ) AS calculated_net_purchase_amount,

            p.source_system,
            p.source_table,
            p.source_row_identifier,
            p.ingestion_batch_id,
            p.ingested_at

        FROM core.fact_purchases AS p

        JOIN core.dim_date AS d
            ON p.date_key = d.date_key

        JOIN core.dim_supplier AS s
            ON p.supplier_key = s.supplier_key

        JOIN core.dim_product AS pr
            ON p.product_key = pr.product_key

        JOIN core.dim_location AS l
            ON p.location_key = l.location_key;
        """
    )

    # ==========================================================
    # 8. Cash transaction analytics
    # ==========================================================
    #
    # FIXED vs. original draft (core.fact_cash_transactions columns
    # are: cash_transaction_key, transaction_id, date_key,
    # cash_account_key, transaction_type, direction, amount,
    # reference_type, reference_id, description, created_by,
    # source_created_at, source_system, ...):
    #   - ct.cash_transaction_id -> ct.transaction_id
    #     (no `cash_transaction_id` column)
    #   - removed ct.category (no such column)
    #   - added ct.direction, the actual IN/OUT column enforced by
    #     ck_fact_cash_transactions_valid_movement_direction
    # ==========================================================

    op.execute(
        """
        CREATE VIEW analytics.v_cash_transactions AS
        SELECT
            ct.cash_transaction_key,
            ct.transaction_id,

            d.date_key,
            d.date AS transaction_date,
            d.year,
            d.quarter,
            d.month,
            d.month_name,

            ca.cash_account_key,
            ca.cash_account_id,
            ca.account_name AS cash_account_name,
            ca.account_type AS cash_account_type,
            ca.owner_id AS cash_account_owner_id,

            ct.transaction_type,
            ct.direction,
            ct.amount,
            ct.reference_type,
            ct.reference_id,
            ct.description,
            ct.created_by,

            ct.source_created_at,
            ct.source_system,
            ct.source_table,
            ct.source_row_identifier,
            ct.ingestion_batch_id,
            ct.ingested_at

        FROM core.fact_cash_transactions AS ct

        JOIN core.dim_date AS d
            ON ct.date_key = d.date_key

        JOIN core.dim_cash_account AS ca
            ON ct.cash_account_key = ca.cash_account_key;
        """
    )

    # ==========================================================
    # 9. Expense analytics
    # ==========================================================
    #
    # FIXED vs. original draft (core.fact_expenses columns are:
    # expense_key, expense_id, date_key, expense_category,
    # description, amount, payment_method, cash_account_key,
    # paid_by, reference, created_by, created_at, source_system,
    # ...):
    #   - e.category -> e.expense_category (no `category` column)
    #   - removed e.notes (no such column); added e.reference instead
    #   - e.source_created_at -> e.created_at
    #     (no `source_created_at` column on this table)
    #   - added e.created_by (exists, was dropped in original draft)
    #   - cash_account_key is NULLABLE on fact_expenses, so the join
    #     changed from inner JOIN to LEFT JOIN to avoid silently
    #     dropping expenses that have no linked cash account
    # ==========================================================

    op.execute(
        """
        CREATE VIEW analytics.v_expenses AS
        SELECT
            e.expense_key,
            e.expense_id,

            d.date_key,
            d.date AS expense_date,
            d.year,
            d.quarter,
            d.month,
            d.month_name,

            ca.cash_account_key,
            ca.cash_account_id,
            ca.account_name AS cash_account_name,
            ca.account_type AS cash_account_type,

            e.expense_category,
            e.amount,
            e.payment_method,
            e.description,
            e.reference,
            e.paid_by,
            e.created_by,

            e.created_at,
            e.source_system,
            e.source_table,
            e.source_row_identifier,
            e.ingestion_batch_id,
            e.ingested_at

        FROM core.fact_expenses AS e

        JOIN core.dim_date AS d
            ON e.date_key = d.date_key

        LEFT JOIN core.dim_cash_account AS ca
            ON e.cash_account_key = ca.cash_account_key;
        """
    )

    # ==========================================================
    # 10. Partner capital analytics
    # ==========================================================
    #
    # FIXED vs. original draft (core.fact_partner_capital columns
    # are: capital_key, capital_transaction_id, date_key,
    # partner_key, cash_account_key, transaction_type, amount,
    # reference_id, notes, created_by, created_at, source_system,
    # ...):
    #   - pc.partner_capital_key -> pc.capital_key
    #     (no `partner_capital_key` column)
    #   - removed pc.description (no such column); added
    #     pc.reference_id and pc.created_by instead (both exist)
    #   - pc.source_created_at -> pc.created_at
    #     (no `source_created_at` column on this table)
    # ==========================================================

    op.execute(
        """
        CREATE VIEW analytics.v_partner_capital AS
        SELECT
            pc.capital_key,
            pc.capital_transaction_id,

            d.date_key,
            d.date AS transaction_date,
            d.year,
            d.quarter,
            d.month,
            d.month_name,

            p.partner_key,
            p.partner_id,
            p.partner_name,

            ca.cash_account_key,
            ca.cash_account_id,
            ca.account_name AS cash_account_name,
            ca.account_type AS cash_account_type,

            pc.transaction_type,
            pc.amount,
            pc.reference_id,
            pc.notes,
            pc.created_by,

            pc.created_at,
            pc.source_system,
            pc.source_table,
            pc.source_row_identifier,
            pc.ingestion_batch_id,
            pc.ingested_at

        FROM core.fact_partner_capital AS pc

        JOIN core.dim_date AS d
            ON pc.date_key = d.date_key

        JOIN core.dim_partner AS p
            ON pc.partner_key = p.partner_key

        JOIN core.dim_cash_account AS ca
            ON pc.cash_account_key = ca.cash_account_key;
        """
    )

    # ==========================================================
    # 11. Stock movement analytics
    # ==========================================================
    #
    # FIXED vs. original draft (core.fact_stock_movements columns
    # are: stock_movement_key, movement_id, date_key, product_key,
    # movement_type, direction, quantity, from_location_key,
    # to_location_key, reference_id, notes, source_system, ...):
    #   - removed sm.reference_type (no such column; only
    #     `reference_id` exists)
    #   - removed sm.moved_by (no such column)
    #   - removed sm.source_created_at (no such column on this
    #     table - only `ingested_at`)
    #   - added sm.direction, the actual IN/OUT column enforced by
    #     ck_fact_stock_movements_valid_movement_direction
    # ==========================================================

    op.execute(
        """
        CREATE VIEW analytics.v_stock_movements AS
        SELECT
            sm.stock_movement_key,
            sm.movement_id,

            d.date_key,
            d.date AS movement_date,
            d.year,
            d.quarter,
            d.month,
            d.month_name,

            p.product_key,
            p.product_id,
            p.product_name,
            p.category AS product_category,
            p.unit AS product_unit,

            fl.location_key AS from_location_key,
            fl.stock_location_id AS from_location_id,
            fl.location_name AS from_location_name,

            tl.location_key AS to_location_key,
            tl.stock_location_id AS to_location_id,
            tl.location_name AS to_location_name,

            sm.movement_type,
            sm.direction,
            sm.quantity,
            sm.reference_id,
            sm.notes,

            sm.source_system,
            sm.source_table,
            sm.source_row_identifier,
            sm.ingestion_batch_id,
            sm.ingested_at

        FROM core.fact_stock_movements AS sm

        JOIN core.dim_date AS d
            ON sm.date_key = d.date_key

        JOIN core.dim_product AS p
            ON sm.product_key = p.product_key

        LEFT JOIN core.dim_location AS fl
            ON sm.from_location_key = fl.location_key

        LEFT JOIN core.dim_location AS tl
            ON sm.to_location_key = tl.location_key;
        """
    )

    # ==========================================================
    # 12. Daily business summary
    # ==========================================================
    #
    # This is intentionally a date-level summary.
    #
    # It does not derive customer balances or overwrite HBMS
    # business-managed aggregates. It summarizes warehouse facts.
    #
    # FIXED vs. original draft:
    #   - cash_in / cash_out CTEs filtered on
    #     `transaction_type = 'IN' / 'OUT'`. The IN/OUT check
    #     constraint (ck_fact_cash_transactions_valid_movement_direction)
    #     is actually on the `direction` column, not
    #     `transaction_type`. Filtering on the wrong column meant
    #     these totals were silently wrong (likely always zero,
    #     since `transaction_type` holds a different vocabulary).
    #     Changed both CTEs to filter on `direction`.
    #
    #   NOTE: the `orders` CTE below still reads core.fact_orders,
    #   which is unverified (see module docstring).
    # ==========================================================

    op.execute(
        """
        CREATE VIEW analytics.v_daily_business_summary AS

        WITH orders AS (
            SELECT
                date_key,
                COUNT(*) AS total_orders,
                COALESCE(SUM(total_amount), 0) AS total_order_amount
            FROM core.fact_orders
            GROUP BY date_key
        ),

        sales AS (
            SELECT
                date_key,
                COALESCE(SUM(line_total), 0) AS total_sales_amount,
                COALESCE(SUM(quantity), 0) AS total_sales_quantity
            FROM core.fact_sales
            GROUP BY date_key
        ),

        payments AS (
            SELECT
                date_key,
                COALESCE(SUM(amount), 0) AS total_payments
            FROM core.fact_payments
            GROUP BY date_key
        ),

        customer_returns AS (
            SELECT
                date_key,
                COUNT(*) AS total_customer_returns,
                COALESCE(SUM(refund_amount), 0) AS total_customer_return_amount,
                COALESCE(SUM(cash_refund), 0) AS total_customer_cash_refund,
                COALESCE(SUM(due_adjustment), 0)
                    AS total_customer_due_adjustment
            FROM core.fact_returns
            WHERE return_type = 'CUSTOMER_RETURN'
            GROUP BY date_key
        ),

        supplier_returns AS (
            SELECT
                date_key,
                COUNT(*) AS total_supplier_returns,
                COALESCE(SUM(refund_amount), 0) AS total_supplier_return_amount
            FROM core.fact_returns
            WHERE return_type = 'SUPPLIER_RETURN'
            GROUP BY date_key
        ),

        purchases AS (
            SELECT
                date_key,
                COUNT(DISTINCT purchase_id) AS total_purchases,
                COALESCE(SUM(line_total), 0) AS total_purchase_amount,
                COALESCE(SUM(quantity), 0) AS total_purchase_quantity
            FROM core.fact_purchases
            GROUP BY date_key
        ),

        expenses AS (
            SELECT
                date_key,
                COALESCE(SUM(amount), 0) AS total_expenses
            FROM core.fact_expenses
            GROUP BY date_key
        ),

        capital AS (
            SELECT
                date_key,

                COALESCE(
                    SUM(
                        CASE
                            WHEN transaction_type = 'CAPITAL'
                            THEN amount
                            ELSE 0
                        END
                    ),
                    0
                ) AS capital_added,

                COALESCE(
                    SUM(
                        CASE
                            WHEN transaction_type = 'WITHDRAWAL'
                            THEN amount
                            ELSE 0
                        END
                    ),
                    0
                ) AS capital_withdrawn

            FROM core.fact_partner_capital
            GROUP BY date_key
        ),

        cash_in AS (
            SELECT
                date_key,
                COALESCE(SUM(amount), 0) AS total_cash_in
            FROM core.fact_cash_transactions
            WHERE direction = 'IN'
            GROUP BY date_key
        ),

        cash_out AS (
            SELECT
                date_key,
                COALESCE(SUM(amount), 0) AS total_cash_out
            FROM core.fact_cash_transactions
            WHERE direction = 'OUT'
            GROUP BY date_key
        )

        SELECT
            d.date_key,
            d.date AS business_date,
            d.year,
            d.quarter,
            d.month,
            d.month_name,
            d.week,
            d.day,
            d.day_name,
            d.is_weekend,

            COALESCE(o.total_orders, 0) AS total_orders,
            COALESCE(o.total_order_amount, 0) AS total_order_amount,

            COALESCE(s.total_sales_amount, 0) AS total_sales_amount,
            COALESCE(s.total_sales_quantity, 0) AS total_sales_quantity,

            COALESCE(p.total_payments, 0) AS total_payments,

            COALESCE(cr.total_customer_returns, 0)
                AS total_customer_returns,
            COALESCE(cr.total_customer_return_amount, 0)
                AS total_customer_return_amount,
            COALESCE(cr.total_customer_cash_refund, 0)
                AS total_customer_cash_refund,
            COALESCE(cr.total_customer_due_adjustment, 0)
                AS total_customer_due_adjustment,

            COALESCE(sr.total_supplier_returns, 0)
                AS total_supplier_returns,
            COALESCE(sr.total_supplier_return_amount, 0)
                AS total_supplier_return_amount,

            COALESCE(pu.total_purchases, 0) AS total_purchases,
            COALESCE(pu.total_purchase_amount, 0)
                AS total_purchase_amount,
            COALESCE(pu.total_purchase_quantity, 0)
                AS total_purchase_quantity,

            COALESCE(e.total_expenses, 0) AS total_expenses,

            COALESCE(cap.capital_added, 0) AS capital_added,
            COALESCE(cap.capital_withdrawn, 0) AS capital_withdrawn,

            COALESCE(ci.total_cash_in, 0) AS total_cash_in,
            COALESCE(co.total_cash_out, 0) AS total_cash_out,

            (
                COALESCE(s.total_sales_amount, 0)
                - COALESCE(cr.total_customer_return_amount, 0)
            ) AS net_sales,

            (
                COALESCE(s.total_sales_amount, 0)
                - COALESCE(cr.total_customer_return_amount, 0)
                - COALESCE(pu.total_purchase_amount, 0)
            ) AS gross_business_margin,

            (
                COALESCE(s.total_sales_amount, 0)
                - COALESCE(cr.total_customer_return_amount, 0)
                - COALESCE(pu.total_purchase_amount, 0)
                - COALESCE(e.total_expenses, 0)
            ) AS operating_result

        FROM core.dim_date AS d

        LEFT JOIN orders AS o
            ON d.date_key = o.date_key

        LEFT JOIN sales AS s
            ON d.date_key = s.date_key

        LEFT JOIN payments AS p
            ON d.date_key = p.date_key

        LEFT JOIN customer_returns AS cr
            ON d.date_key = cr.date_key

        LEFT JOIN supplier_returns AS sr
            ON d.date_key = sr.date_key

        LEFT JOIN purchases AS pu
            ON d.date_key = pu.date_key

        LEFT JOIN expenses AS e
            ON d.date_key = e.date_key

        LEFT JOIN capital AS cap
            ON d.date_key = cap.date_key

        LEFT JOIN cash_in AS ci
            ON d.date_key = ci.date_key

        LEFT JOIN cash_out AS co
            ON d.date_key = co.date_key;
        """
    )


def downgrade() -> None:
    # Drop views created by this revision.
    op.execute("DROP VIEW IF EXISTS analytics.v_daily_business_summary")
    op.execute("DROP VIEW IF EXISTS analytics.v_stock_movements")
    op.execute("DROP VIEW IF EXISTS analytics.v_partner_capital")
    op.execute("DROP VIEW IF EXISTS analytics.v_expenses")
    op.execute("DROP VIEW IF EXISTS analytics.v_cash_transactions")
    op.execute("DROP VIEW IF EXISTS analytics.v_return_items")
    op.execute("DROP VIEW IF EXISTS analytics.v_orders")
    op.execute("DROP VIEW IF EXISTS analytics.v_sales")

    # Restore the revision 007 order-level v_sales view.
    # NOTE: unchanged from the original draft - depends on
    # core.fact_orders, which is unverified (see module docstring).
    op.execute(
        """
        CREATE VIEW analytics.v_sales AS
        SELECT
            o.order_key,
            o.order_id,
            d.date AS order_date,

            c.customer_key,
            c.customer_id,
            c.customer_name,

            o.subtotal,
            o.invoice_discount,
            o.delivery_charge,
            o.total_amount,

            o.order_status,
            o.collected_by,
            o.source_created_at

        FROM core.fact_orders AS o

        JOIN core.dim_date AS d
            ON o.date_key = d.date_key

        LEFT JOIN core.dim_customer AS c
            ON o.customer_key = c.customer_key;
        """
    )

    # Restore the revision 007 daily summary.
    # NOTE: unchanged from the original draft - depends on
    # core.fact_orders, which is unverified (see module docstring).
    op.execute(
        """
        CREATE VIEW analytics.v_daily_business_summary AS
        WITH sales AS (
            SELECT
                date_key,
                COUNT(*) AS total_orders,
                COALESCE(SUM(total_amount), 0) AS total_sales
            FROM core.fact_orders
            GROUP BY date_key
        ),

        payments AS (
            SELECT
                date_key,
                COALESCE(SUM(amount), 0) AS total_payments
            FROM core.fact_payments
            GROUP BY date_key
        ),

        returns AS (
            SELECT
                date_key,
                COUNT(*) AS total_returns,
                COALESCE(SUM(refund_amount), 0) AS total_return_amount,
                COALESCE(SUM(cash_refund), 0) AS total_cash_refund,
                COALESCE(SUM(due_adjustment), 0)
                    AS total_due_adjustment
            FROM core.fact_returns
            GROUP BY date_key
        ),

        purchases AS (
            SELECT
                date_key,
                COUNT(DISTINCT purchase_id) AS total_purchases,
                COALESCE(SUM(line_total), 0)
                    AS total_purchase_amount
            FROM core.fact_purchases
            GROUP BY date_key
        )

        SELECT
            d.date_key,
            d.date AS business_date,

            COALESCE(s.total_orders, 0) AS total_orders,
            COALESCE(s.total_sales, 0) AS total_sales,

            COALESCE(p.total_payments, 0) AS total_payments,

            COALESCE(r.total_returns, 0) AS total_returns,
            COALESCE(r.total_return_amount, 0)
                AS total_return_amount,
            COALESCE(r.total_cash_refund, 0)
                AS total_cash_refund,
            COALESCE(r.total_due_adjustment, 0)
                AS total_due_adjustment,

            COALESCE(b.total_purchases, 0) AS total_purchases,
            COALESCE(b.total_purchase_amount, 0)
                AS total_purchase_amount,

            (
                COALESCE(s.total_sales, 0)
                - COALESCE(r.total_return_amount, 0)
            ) AS net_sales,

            (
                COALESCE(s.total_sales, 0)
                - COALESCE(r.total_return_amount, 0)
                - COALESCE(b.total_purchase_amount, 0)
            ) AS gross_business_margin

        FROM core.dim_date AS d

        LEFT JOIN sales AS s
            ON d.date_key = s.date_key

        LEFT JOIN payments AS p
            ON d.date_key = p.date_key

        LEFT JOIN returns AS r
            ON d.date_key = r.date_key

        LEFT JOIN purchases AS b
            ON d.date_key = b.date_key;
        """
    )