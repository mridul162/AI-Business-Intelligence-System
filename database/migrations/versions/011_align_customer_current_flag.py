"""Align the customer dimension current-record flag with the warehouse contract.

Revision ID: 011_align_customer_current_flag
Revises: 010_add_security_boundaries
Create Date: 2026-09-21
"""

from alembic import op


revision = "011_align_customer_current_flag"
down_revision = "010_add_security_boundaries"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'core'
                  AND table_name = 'dim_customer'
                  AND column_name = 'active'
            ) AND NOT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'core'
                  AND table_name = 'dim_customer'
                  AND column_name = 'is_current'
            ) THEN
                ALTER TABLE core.dim_customer RENAME COLUMN active TO is_current;
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        DO $$
        DECLARE
            view_record RECORD;
            needs_timestamp_upgrade BOOLEAN;
        BEGIN
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'core'
                  AND data_type = 'timestamp without time zone'
                  AND (
                      (table_name = 'dim_customer' AND column_name IN ('valid_from', 'valid_to'))
                      OR (table_name = 'dim_product' AND column_name IN ('valid_from', 'valid_to'))
                      OR (table_name = 'fact_orders' AND column_name IN ('source_created_at', 'ingested_at'))
                      OR (table_name = 'fact_sales' AND column_name = 'ingested_at')
                  )
            ) INTO needs_timestamp_upgrade;

            IF needs_timestamp_upgrade THEN
                CREATE TEMP TABLE _aibi_saved_views (
                    view_name TEXT PRIMARY KEY,
                    view_definition TEXT NOT NULL
                ) ON COMMIT DROP;

                INSERT INTO _aibi_saved_views (view_name, view_definition)
                SELECT table_name,
                       pg_get_viewdef(format('%I.%I', table_schema, table_name)::regclass, TRUE)
                FROM information_schema.views
                WHERE table_schema = 'analytics';

                FOR view_record IN
                    SELECT view_name
                    FROM _aibi_saved_views
                    ORDER BY view_name
                LOOP
                    EXECUTE format('DROP VIEW analytics.%I CASCADE', view_record.view_name);
                END LOOP;

                ALTER TABLE core.dim_customer
                    ALTER COLUMN valid_from TYPE TIMESTAMP WITH TIME ZONE
                    USING valid_from AT TIME ZONE 'UTC';
                ALTER TABLE core.dim_customer
                    ALTER COLUMN valid_to TYPE TIMESTAMP WITH TIME ZONE
                    USING valid_to AT TIME ZONE 'UTC';
                ALTER TABLE core.dim_product
                    ALTER COLUMN valid_from TYPE TIMESTAMP WITH TIME ZONE
                    USING valid_from AT TIME ZONE 'UTC';
                ALTER TABLE core.dim_product
                    ALTER COLUMN valid_to TYPE TIMESTAMP WITH TIME ZONE
                    USING valid_to AT TIME ZONE 'UTC';
                ALTER TABLE core.fact_orders
                    ALTER COLUMN source_created_at TYPE TIMESTAMP WITH TIME ZONE
                    USING source_created_at AT TIME ZONE 'UTC';
                ALTER TABLE core.fact_orders
                    ALTER COLUMN ingested_at TYPE TIMESTAMP WITH TIME ZONE
                    USING ingested_at AT TIME ZONE 'UTC';
                ALTER TABLE core.fact_sales
                    ALTER COLUMN ingested_at TYPE TIMESTAMP WITH TIME ZONE
                    USING ingested_at AT TIME ZONE 'UTC';

                FOR view_record IN
                    SELECT view_name, view_definition
                    FROM _aibi_saved_views
                    WHERE right(view_name, 9) = '_unscoped'
                    ORDER BY view_name
                LOOP
                    EXECUTE format(
                        'CREATE VIEW analytics.%I AS %s',
                        view_record.view_name,
                        view_record.view_definition
                    );
                END LOOP;

                FOR view_record IN
                    SELECT view_name, view_definition
                    FROM _aibi_saved_views
                    WHERE right(view_name, 9) <> '_unscoped'
                    ORDER BY view_name
                LOOP
                    EXECUTE format(
                        'CREATE VIEW analytics.%I AS %s',
                        view_record.view_name,
                        view_record.view_definition
                    );
                END LOOP;
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'core'
                  AND table_name = 'dim_customer'
                  AND column_name = 'is_current'
            ) AND NOT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'core'
                  AND table_name = 'dim_customer'
                  AND column_name = 'active'
            ) THEN
                ALTER TABLE core.dim_customer RENAME COLUMN is_current TO active;
            END IF;
        END
        $$;
        """
    )
