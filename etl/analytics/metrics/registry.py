"""
Central registry for BI metric definitions.
"""

from __future__ import annotations

from etl.analytics.metrics.definitions import MetricDefinition


METRIC_REGISTRY: dict[str, MetricDefinition] = {
    "total_orders": MetricDefinition(
        name="total_orders",
        display_name="Total Orders",
        description=(
            "Total number of unique customer orders."
        ),
        source_view="analytics.v_orders",
        aggregation="count_distinct",
        expression="COUNT(DISTINCT order_id)",
        filters=(),
        supported_dimensions=(
            "customer_id",
            "customer_name",
            "order_status",
            "collected_by",
        ),
        supported_time_grains=(
            "daily",
            "weekly",
            "monthly",
            "quarterly",
            "yearly",
        ),
        output_field="total_orders",
    ),

    "gross_sales": MetricDefinition(
        name="gross_sales",
        display_name="Gross Sales",
        description=(
            "Total sales value before return deductions."
        ),
        source_view="analytics.v_sales",
        aggregation="sum",
        expression="SUM(gross_sales)",
        filters=(),
        supported_dimensions=(
            "customer_id",
            "customer_name",
            "product_id",
            "product_name",
            # FIXED: analytics.v_sales exposes this column as
            # `product_category` (p.category AS product_category),
            # not `category`.
            "product_category",
            "location_id",
            "location_name",
        ),
        supported_time_grains=(
            "daily",
            "weekly",
            "monthly",
            "quarterly",
            "yearly",
        ),
        output_field="gross_sales",
        aliases=("revenue", "sales", "earn", "earnings", "income"),
    ),

    "net_sales": MetricDefinition(
        name="net_sales",
        display_name="Net Sales",
        description=(
            "Gross sales after deducting customer return amounts."
        ),
        source_view="analytics.v_daily_business_summary",
        aggregation="sum",
        expression="SUM(net_sales)",
        filters=(),
        supported_dimensions=(),
        supported_time_grains=(
            "daily",
            "weekly",
            "monthly",
            "quarterly",
            "yearly",
        ),
        output_field="net_sales",
        aliases=("net revenue", "earn", "earnings", "income"),
    ),

    "total_payments": MetricDefinition(
        name="total_payments",
        display_name="Total Payments",
        description=(
            "Total amount received through recorded payments."
        ),
        source_view="analytics.v_payments",
        aggregation="sum",
        expression="SUM(amount)",
        filters=(),
        supported_dimensions=(
            "customer_id",
            "customer_name",
            "cash_account_id",
            "cash_account_name",
            "payment_method",
            "collected_by",
        ),
        supported_time_grains=(
            "daily",
            "weekly",
            "monthly",
            "quarterly",
            "yearly",
        ),
        output_field="total_payments",
        aliases=("collections",),
    ),

    "total_returns": MetricDefinition(
        name="total_returns",
        display_name="Total Returns",
        description=(
            "Total number of customer and supplier return transactions."
        ),
        source_view="analytics.v_returns",
        aggregation="count_distinct",
        expression="COUNT(DISTINCT return_id)",
        filters=(),
        supported_dimensions=(
            "return_type",
            "customer_id",
            "customer_name",
            "location_id",
            "location_name",
            "cash_account_id",
            "cash_account_name",
            "status",
            "returned_by",
        ),
        supported_time_grains=(
            "daily",
            "weekly",
            "monthly",
            "quarterly",
            "yearly",
        ),
        output_field="total_returns",
    ),

    "return_amount": MetricDefinition(
        name="return_amount",
        display_name="Return Amount",
        description=(
            "Total financial value of recorded returns."
        ),
        source_view="analytics.v_returns",
        aggregation="sum",
        expression="SUM(refund_amount)",
        filters=(),
        supported_dimensions=(
            "return_type",
            "customer_id",
            "customer_name",
            "location_id",
            "location_name",
            "status",
        ),
        supported_time_grains=(
            "daily",
            "weekly",
            "monthly",
            "quarterly",
            "yearly",
        ),
        output_field="return_amount",
    ),

    "cash_refund": MetricDefinition(
        name="cash_refund",
        display_name="Cash Refund",
        description=(
            "Total return value refunded directly in cash."
        ),
        source_view="analytics.v_returns",
        aggregation="sum",
        expression="SUM(cash_refund)",
        filters=(),
        supported_dimensions=(
            "return_type",
            "customer_id",
            "customer_name",
            "cash_account_id",
            "cash_account_name",
        ),
        supported_time_grains=(
            "daily",
            "weekly",
            "monthly",
            "quarterly",
            "yearly",
        ),
        output_field="cash_refund",
    ),

    "due_adjustment": MetricDefinition(
        name="due_adjustment",
        display_name="Due Adjustment",
        description=(
            "Total return value adjusted against outstanding dues."
        ),
        source_view="analytics.v_returns",
        aggregation="sum",
        expression="SUM(due_adjustment)",
        filters=(),
        supported_dimensions=(
            "return_type",
            "customer_id",
            "customer_name",
            "status",
        ),
        supported_time_grains=(
            "daily",
            "weekly",
            "monthly",
            "quarterly",
            "yearly",
        ),
        output_field="due_adjustment",
    ),

    "total_purchases": MetricDefinition(
        name="total_purchases",
        display_name="Total Purchases",
        description=(
            "Total value of purchased inventory items."
        ),
        source_view="analytics.v_purchases",
        aggregation="sum",
        expression="SUM(line_total)",
        filters=(),
        supported_dimensions=(
            "supplier_id",
            "supplier_name",
            "product_id",
            "product_name",
            "location_id",
            "location_name",
        ),
        supported_time_grains=(
            "daily",
            "weekly",
            "monthly",
            "quarterly",
            "yearly",
        ),
        output_field="total_purchases",
    ),

    "purchase_transactions": MetricDefinition(
        name="purchase_transactions",
        display_name="Purchase Transactions",
        description=(
            "Total number of unique purchase transactions."
        ),
        source_view="analytics.v_purchases",
        aggregation="count_distinct",
        expression="COUNT(DISTINCT purchase_id)",
        filters=(),
        supported_dimensions=(
            "supplier_id",
            "supplier_name",
            "location_id",
            "location_name",
        ),
        supported_time_grains=(
            "daily",
            "weekly",
            "monthly",
            "quarterly",
            "yearly",
        ),
        output_field="purchase_transactions",
    ),

    "cash_in": MetricDefinition(
        name="cash_in",
        display_name="Cash In",
        description=(
            "Total incoming cash transactions."
        ),
        source_view="analytics.v_cash_transactions",
        aggregation="sum",
        expression="SUM(amount)",
        filters=(
            "direction = 'IN'",
        ),
        supported_dimensions=(
            "cash_account_id",
            "cash_account_name",
            "transaction_type",
        ),
        supported_time_grains=(
            "daily",
            "weekly",
            "monthly",
            "quarterly",
            "yearly",
        ),
        output_field="cash_in",
        aliases=("cash inflow",),
    ),

    "cash_out": MetricDefinition(
        name="cash_out",
        display_name="Cash Out",
        description=(
            "Total outgoing cash transactions."
        ),
        source_view="analytics.v_cash_transactions",
        aggregation="sum",
        expression="SUM(amount)",
        filters=(
            "direction = 'OUT'",
        ),
        supported_dimensions=(
            "cash_account_id",
            "cash_account_name",
            "transaction_type",
        ),
        supported_time_grains=(
            "daily",
            "weekly",
            "monthly",
            "quarterly",
            "yearly",
        ),
        output_field="cash_out",
        aliases=("cash outflow",),
    ),

    "total_expenses": MetricDefinition(
        name="total_expenses",
        display_name="Total Expenses",
        description=(
            "Total recorded business expenses."
        ),
        source_view="analytics.v_expenses",
        aggregation="sum",
        expression="SUM(amount)",
        filters=(),
        supported_dimensions=(
            "expense_category",
            "cash_account_id",
            "cash_account_name",
            "paid_by",
        ),
        supported_time_grains=(
            "daily",
            "weekly",
            "monthly",
            "quarterly",
            "yearly",
        ),
        output_field="total_expenses",
    ),

    "partner_capital_in": MetricDefinition(
        name="partner_capital_in",
        display_name="Partner Capital In",
        description=(
            "Total capital contributed by business partners."
        ),
        source_view="analytics.v_partner_capital",
        aggregation="sum",
        expression="SUM(amount)",
        # FIXED: core.fact_partner_capital (and the view built on it)
        # has no `direction` column. The IN/OUT vocabulary for
        # capital movements lives on `transaction_type`, with values
        # 'CAPITAL' (contribution) and 'WITHDRAWAL' — see the
        # `capital` CTE in analytics.v_daily_business_summary, which
        # is the source of truth for this vocabulary.
        filters=(
            "transaction_type = 'CAPITAL'",
        ),
        supported_dimensions=(
            "partner_id",
            "partner_name",
            "cash_account_id",
            "cash_account_name",
            "transaction_type",
        ),
        supported_time_grains=(
            "daily",
            "weekly",
            "monthly",
            "quarterly",
            "yearly",
        ),
        output_field="partner_capital_in",
    ),

    "partner_capital_out": MetricDefinition(
        name="partner_capital_out",
        display_name="Partner Capital Out",
        description=(
            "Total capital withdrawn by business partners."
        ),
        source_view="analytics.v_partner_capital",
        aggregation="sum",
        expression="SUM(amount)",
        # FIXED: see partner_capital_in above — no `direction`
        # column on this view; withdrawals are transaction_type =
        # 'WITHDRAWAL'.
        filters=(
            "transaction_type = 'WITHDRAWAL'",
        ),
        supported_dimensions=(
            "partner_id",
            "partner_name",
            "cash_account_id",
            "cash_account_name",
            "transaction_type",
        ),
        supported_time_grains=(
            "daily",
            "weekly",
            "monthly",
            "quarterly",
            "yearly",
        ),
        output_field="partner_capital_out",
    ),

    "stock_in_quantity": MetricDefinition(
        name="stock_in_quantity",
        display_name="Stock In Quantity",
        description=(
            "Total quantity moved into inventory locations."
        ),
        source_view="analytics.v_stock_movements",
        aggregation="sum",
        expression="SUM(quantity)",
        filters=(
            "direction = 'IN'",
        ),
        supported_dimensions=(
            "product_id",
            "product_name",
            "from_location_id",
            "from_location_name",
            "to_location_id",
            "to_location_name",
            "movement_type",
        ),
        supported_time_grains=(
            "daily",
            "weekly",
            "monthly",
            "quarterly",
            "yearly",
        ),
        output_field="stock_in_quantity",
    ),

    "stock_out_quantity": MetricDefinition(
        name="stock_out_quantity",
        display_name="Stock Out Quantity",
        description=(
            "Total quantity moved out of inventory locations."
        ),
        source_view="analytics.v_stock_movements",
        aggregation="sum",
        expression="SUM(quantity)",
        filters=(
            "direction = 'OUT'",
        ),
        supported_dimensions=(
            "product_id",
            "product_name",
            "from_location_id",
            "from_location_name",
            "to_location_id",
            "to_location_name",
            "movement_type",
        ),
        supported_time_grains=(
            "daily",
            "weekly",
            "monthly",
            "quarterly",
            "yearly",
        ),
        output_field="stock_out_quantity",
    ),

    "gross_business_margin": MetricDefinition(
        name="gross_business_margin",
        display_name="Gross Business Margin",
        description=(
            "Net sales minus purchase amount. This is a business-level "
            "margin indicator and should not be interpreted as accounting "
            "gross profit unless the underlying cost model supports that."
        ),
        source_view="analytics.v_daily_business_summary",
        aggregation="sum",
        expression="SUM(gross_business_margin)",
        filters=(),
        supported_dimensions=(),
        supported_time_grains=(
            "daily",
            "weekly",
            "monthly",
            "quarterly",
            "yearly",
        ),
        output_field="gross_business_margin",
        aliases=("profit", "earn", "earnings", "income"),
    ),
}


def get_metric(
    metric_name: str,
) -> MetricDefinition:
    """
    Return one metric definition.

    Raises:
        KeyError: If the metric is not registered.
    """

    try:
        return METRIC_REGISTRY[metric_name]
    except KeyError as exc:
        raise KeyError(
            f"Unknown metric: {metric_name}"
        ) from exc


def list_metrics() -> tuple[MetricDefinition, ...]:
    """Return all registered metric definitions."""

    return tuple(
        METRIC_REGISTRY.values()
    )