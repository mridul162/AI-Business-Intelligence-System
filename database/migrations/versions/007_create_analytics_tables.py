"""Create analytics views for BI reporting.

Revision ID: 007_analytics_tables
Revises: 006_core_tables
Create Date: 2026-08-18
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "007_analytics_tables"
down_revision = "006_core_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---------------------------------------------------------
    # 1. Sales analytics
    # ---------------------------------------------------------
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

    # ---------------------------------------------------------
    # 2. Payment analytics
    # ---------------------------------------------------------
    op.execute(
        """
        CREATE VIEW analytics.v_payments AS
        SELECT
            p.payment_key,
            p.payment_id,
            d.date AS payment_date,

            p.order_id,

            c.customer_key,
            c.customer_id,
            c.customer_name,

            ca.cash_account_key,
            ca.cash_account_id,
            ca.account_name AS cash_account_name,

            p.amount,
            p.payment_method,
            p.collected_by,
            p.notes

        FROM core.fact_payments AS p

        JOIN core.dim_date AS d
            ON p.date_key = d.date_key

        LEFT JOIN core.dim_customer AS c
            ON p.customer_key = c.customer_key

        LEFT JOIN core.dim_cash_account AS ca
            ON p.cash_account_key = ca.cash_account_key;
        """
    )

    # ---------------------------------------------------------
    # 3. Return analytics
    # ---------------------------------------------------------
    op.execute(
        """
        CREATE VIEW analytics.v_returns AS
        SELECT
            r.return_key,
            r.return_id,
            d.date AS return_date,

            r.return_type,
            r.order_id,
            r.purchase_id,

            c.customer_key,
            c.customer_id,
            c.customer_name,

            l.location_key,
            l.stock_location_id AS location_id,
            l.location_name,

            ca.cash_account_key,
            ca.cash_account_id,
            ca.account_name AS cash_account_name,

            r.refund_amount,
            r.due_adjustment,
            r.cash_refund,
            r.returned_by,
            r.reason,
            r.status,

            r.source_system,
            r.source_created_at
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

    # ---------------------------------------------------------
    # 4. Purchase analytics
    # ---------------------------------------------------------
    op.execute(
        """
        CREATE VIEW analytics.v_purchases AS
        SELECT
            p.purchase_key,
            p.purchase_id,
            p.purchase_item_id,
            d.date AS purchase_date,

            s.supplier_key,
            s.supplier_id,
            s.supplier_name,

            pr.product_key,
            pr.product_id,
            pr.product_name,

            l.location_key,
            l.stock_location_id AS location_id,
            l.location_name,

            p.quantity,
            p.unit_cost,
            p.item_discount,
            p.line_total

        FROM core.fact_purchases AS p

        JOIN core.dim_date AS d
            ON p.date_key = d.date_key

        LEFT JOIN core.dim_supplier AS s
            ON p.supplier_key = s.supplier_key

        JOIN core.dim_product AS pr
            ON p.product_key = pr.product_key

        JOIN core.dim_location AS l
            ON p.location_key = l.location_key;
        """
    )

    # ---------------------------------------------------------
    # 5. Daily business summary
    # ---------------------------------------------------------
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
                COALESCE(SUM(due_adjustment), 0) AS total_due_adjustment
            FROM core.fact_returns
            GROUP BY date_key
        ),

        purchases AS (
            SELECT
                date_key,
                COUNT(DISTINCT purchase_id) AS total_purchases,
                COALESCE(SUM(line_total), 0) AS total_purchase_amount
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
            COALESCE(r.total_return_amount, 0) AS total_return_amount,
            COALESCE(r.total_cash_refund, 0) AS total_cash_refund,
            COALESCE(r.total_due_adjustment, 0) AS total_due_adjustment,

            COALESCE(b.total_purchases, 0) AS total_purchases,
            COALESCE(b.total_purchase_amount, 0) AS total_purchase_amount,

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


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS analytics.v_daily_business_summary")
    op.execute("DROP VIEW IF EXISTS analytics.v_purchases")
    op.execute("DROP VIEW IF EXISTS analytics.v_returns")
    op.execute("DROP VIEW IF EXISTS analytics.v_payments")
    op.execute("DROP VIEW IF EXISTS analytics.v_sales")