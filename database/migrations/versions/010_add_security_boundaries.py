"""Add tenants, users, and a single-tenant analytics boundary.

The existing Hasanah Mart warehouse is single-tenant. This migration gives
it an explicit tenant identity and wraps the existing analytics views with a
trusted tenant_id column. Future ingestion migrations should populate the
column from the authenticated tenant rather than relying on this seed value.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "010_add_security_boundaries"
down_revision = "009_extend_analytics_views"
branch_labels = None
depends_on = None

HASANAH_TENANT_ID = "00000000-0000-0000-0000-000000000001"
VIEW_NAMES = (
    "v_orders",
    "v_sales",
    "v_payments",
    "v_returns",
    "v_return_items",
    "v_purchases",
    "v_cash_transactions",
    "v_expenses",
    "v_partner_capital",
    "v_stock_movements",
    "v_daily_business_summary",
)


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("tenant_id", sa.UUID(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema="core",
    )
    op.create_table(
        "users",
        sa.Column("user_id", sa.UUID(), primary_key=True),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["core.tenants.tenant_id"]),
        sa.UniqueConstraint("tenant_id", "email"),
        schema="core",
    )
    op.execute(
        """
        INSERT INTO core.tenants (tenant_id, name)
        VALUES ('00000000-0000-0000-0000-000000000001', 'Hasanah Mart')
        """
    )

    for view_name in VIEW_NAMES:
        op.execute(
            f"ALTER VIEW analytics.{view_name} "
            f"RENAME TO {view_name}_unscoped"
        )
        op.execute(
            f"""
            CREATE VIEW analytics.{view_name} AS
            SELECT
                '{HASANAH_TENANT_ID}'::uuid AS tenant_id,
                source_view.*
            FROM analytics.{view_name}_unscoped AS source_view
            """
        )


def downgrade() -> None:
    for view_name in reversed(VIEW_NAMES):
        op.execute(f"DROP VIEW IF EXISTS analytics.{view_name}")
        op.execute(
            f"ALTER VIEW analytics.{view_name}_unscoped RENAME TO {view_name}"
        )
    op.drop_table("users", schema="core")
    op.drop_table("tenants", schema="core")