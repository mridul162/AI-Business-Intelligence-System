from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from etl.data_quality.checks.schema import (
    columns_exist_check,
    expected_column_types_check,
    required_not_null_columns_check,
    table_exists_check,
    view_exists_check,
)
from etl.data_quality.models import DataQualityResult


REQUIRED_WAREHOUSE_TABLES = [
    "core.dim_date",
    "core.dim_customer",
    "core.dim_product",
    "core.dim_supplier",
    "core.dim_partner",
    "core.dim_location",
    "core.dim_cash_account",
    "core.fact_orders",
    "core.fact_sales",
    "core.fact_payments",
    "core.fact_purchases",
    "core.fact_returns",
    "core.fact_return_items",
    "core.fact_stock_movements",
    "core.fact_cash_transactions",
    "core.fact_expenses",
    "core.fact_partner_capital",
]

REQUIRED_ANALYTICAL_VIEWS = [
    "analytics.v_orders",
    "analytics.v_sales",
    "analytics.v_payments",
    "analytics.v_returns",
    "analytics.v_purchases",
    "analytics.v_daily_business_summary",
]

REQUIRED_WAREHOUSE_COLUMN_TYPES = {
    "core.dim_date": {
        "date_key": "integer",
        "date": "date",
        "year": "smallint",
        "quarter": "smallint",
        "month": "smallint",
        "month_number": "smallint",
        "month_name": "character varying(20)",
        "week": "smallint",
        "day": "smallint",
        "day_name": "character varying(20)",
        "is_weekend": "boolean",
    },
    "core.dim_customer": {
        "customer_key": "bigint",
        "customer_id": "character varying(50)",
        "customer_name": "text",
        "phone": "text",
        "address": "text",
        "status": "text",
        "valid_from": "timestamp with time zone",
        "valid_to": "timestamp with time zone",
        "is_current": "boolean",
    },
    "core.dim_product": {
        "product_key": "bigint",
        "product_id": "character varying(50)",
        "product_name": "text",
        "category": "text",
        "unit": "text",
        "current_selling_price": "numeric(14,2)",
        "current_cost_price": "numeric(14,2)",
        "opening_stock": "numeric(14,3)",
        "reorder_level": "numeric(14,3)",
        "active": "text",
        "valid_from": "timestamp with time zone",
        "valid_to": "timestamp with time zone",
        "is_current": "boolean",
    },
    "core.fact_orders": {
        "order_key": "bigint",
        "order_id": "character varying(50)",
        "date_key": "integer",
        "customer_key": "bigint",
        "subtotal": "numeric(14,2)",
        "invoice_discount": "numeric(14,2)",
        "delivery_charge": "numeric(14,2)",
        "total_amount": "numeric(14,2)",
        "order_status": "text",
        "collected_by": "text",
        "source_created_at": "timestamp with time zone",
        "source_system": "text",
        "source_table": "text",
        "source_row_identifier": "text",
        "ingestion_batch_id": "uuid",
        "ingested_at": "timestamp with time zone",
    },
    "core.fact_sales": {
        "sales_key": "bigint",
        "order_id": "character varying(50)",
        "order_item_id": "character varying(50)",
        "date_key": "integer",
        "customer_key": "bigint",
        "product_key": "bigint",
        "location_key": "bigint",
        "quantity": "numeric(14,3)",
        "unit_price": "numeric(14,2)",
        "item_discount": "numeric(14,2)",
        "line_total": "numeric(14,2)",
        "gross_sales": "numeric(14,2)",
        "unit_cost": "numeric(14,2)",
        "cogs": "numeric(14,2)",
        "source_system": "text",
        "source_table": "text",
        "source_row_identifier": "text",
        "ingestion_batch_id": "uuid",
        "ingested_at": "timestamp with time zone",
    },
}

REQUIRED_NON_NULL_COLUMNS = {
    "core.dim_date": ["date_key", "date", "year", "quarter", "month", "month_number", "month_name", "week", "day", "day_name", "is_weekend"],
    "core.dim_customer": ["customer_key", "customer_id", "customer_name", "valid_from", "is_current"],
    "core.dim_product": ["product_key", "product_id", "product_name", "valid_from", "is_current"],
    "core.fact_orders": ["order_key", "order_id", "date_key", "subtotal", "invoice_discount", "delivery_charge", "total_amount", "order_status", "source_system", "source_table", "ingestion_batch_id", "ingested_at"],
    "core.fact_sales": ["sales_key", "order_id", "order_item_id", "date_key", "product_key", "location_key", "quantity", "unit_price", "item_discount", "line_total", "gross_sales", "unit_cost", "cogs", "source_system", "source_table", "ingestion_batch_id", "ingested_at"],
}


def warehouse_structure_check(session: Session) -> DataQualityResult:
    """Validate required warehouse tables, views, and schema elements in the live database."""
    failures: list[str] = []
    warnings: list[str] = []

    for table_name in REQUIRED_WAREHOUSE_TABLES:
        result = table_exists_check(session, table_name)
        if result.status != "PASS":
            failures.append(result.message)

    for view_name in REQUIRED_ANALYTICAL_VIEWS:
        result = view_exists_check(session, view_name)
        if result.status != "PASS":
            failures.append(result.message)

    for table_name, expected_types in REQUIRED_WAREHOUSE_COLUMN_TYPES.items():
        result = expected_column_types_check(session, table_name, expected_types)
        if result.status != "PASS":
            failures.append(result.message)

    for table_name, required_columns in REQUIRED_NON_NULL_COLUMNS.items():
        result = required_not_null_columns_check(session, table_name, required_columns)
        if result.status != "PASS":
            failures.append(result.message)

    if failures:
        return DataQualityResult(
            check_name="warehouse_structure_check",
            status="FAIL",
            severity="ERROR",
            affected_rows=max(1, len(failures)),
            message="; ".join(failures),
        )

    if warnings:
        return DataQualityResult(
            check_name="warehouse_structure_check",
            status="WARNING",
            severity="WARNING",
            affected_rows=max(1, len(warnings)),
            message="; ".join(warnings),
        )

    return DataQualityResult(
        check_name="warehouse_structure_check",
        status="PASS",
        severity="INFO",
        message="Warehouse schema and structural validation passed.",
    )


def analytical_view_columns_check(session: Session, view_name: str, required_columns: list[str]) -> DataQualityResult:
    """Check required columns exist on an analytical view."""
    return columns_exist_check(session, view_name, required_columns)
