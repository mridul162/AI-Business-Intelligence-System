"""
Financial reconciliation validation for the warehouse.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass
class ReconciliationResult:
    """Result of one financial reconciliation."""

    metric_name: str
    source_value: Decimal
    warehouse_value: Decimal

    @property
    def difference(self) -> Decimal:
        """Return the reconciliation difference."""

        return (
            self.source_value
            - self.warehouse_value
        )

    @property
    def is_valid(self) -> bool:
        """Return whether the values reconcile."""

        return self.difference == Decimal("0")


class ReconciliationValidator:
    """
    Reconcile selected financial metrics between staging
    and warehouse facts.
    """

    RECONCILIATIONS = (
        {
            "name": "order_total_amount",
            "source_sql": """
                SELECT COALESCE(
                    SUM(total_amount),
                    0
                )
                FROM (
                    SELECT DISTINCT ON (order_id)
                        order_id,
                        total_amount
                    FROM staging.stg_orders
                    WHERE record_status = 'pending'
                    ORDER BY
                        order_id,
                        ingested_at DESC,
                        stg_order_id DESC
                ) AS latest_orders
            """,
            "warehouse_sql": """
                SELECT COALESCE(
                    SUM(total_amount),
                    0
                )
                FROM core.fact_orders
            """,
        },
        {
            "name": "payment_amount",
            "source_sql": """
                SELECT COALESCE(
                    SUM(amount),
                    0
                )
                FROM (
                    SELECT DISTINCT ON (payment_id)
                        payment_id,
                        amount
                    FROM staging.stg_payments
                    WHERE record_status = 'pending'
                    ORDER BY
                        payment_id,
                        ingested_at DESC,
                        stg_payment_id DESC
                ) AS latest_payments
            """,
            "warehouse_sql": """
                SELECT COALESCE(
                    SUM(amount),
                    0
                )
                FROM core.fact_payments
            """,
        },
        {
            "name": "return_refund_amount",
            "source_sql": """
                SELECT COALESCE(
                    SUM(refund_amount),
                    0
                )
                FROM (
                    SELECT DISTINCT ON (return_id)
                        return_id,
                        refund_amount
                    FROM staging.stg_returns
                    WHERE record_status = 'pending'
                    ORDER BY
                        return_id,
                        ingested_at DESC,
                        stg_return_id DESC
                ) AS latest_returns
            """,
            "warehouse_sql": """
                SELECT COALESCE(
                    SUM(refund_amount),
                    0
                )
                FROM core.fact_returns
            """,
        },
        {
            "name": "purchase_line_total",
            "source_sql": """
                SELECT COALESCE(
                    SUM(line_amount),
                    0
                )
                FROM (
                    SELECT DISTINCT ON (purchase_item_id)
                        purchase_item_id,
                        line_amount
                    FROM staging.stg_purchase_items
                    WHERE record_status = 'pending'
                    ORDER BY
                        purchase_item_id,
                        ingested_at DESC,
                        stg_purchase_item_id DESC
                ) AS latest_purchase_items
            """,
            "warehouse_sql": """
                SELECT COALESCE(
                    SUM(line_total),
                    0
                )
                FROM core.fact_purchases
            """,
        },
        {
            "name": "expense_amount",
            "source_sql": """
                SELECT COALESCE(
                    SUM(amount),
                    0
                )
                FROM (
                    SELECT DISTINCT ON (expense_id)
                        expense_id,
                        amount
                    FROM staging.stg_expenses
                    WHERE record_status = 'pending'
                    ORDER BY
                        expense_id,
                        ingested_at DESC,
                        stg_expense_id DESC
                ) AS latest_expenses
            """,
            "warehouse_sql": """
                SELECT COALESCE(
                    SUM(amount),
                    0
                )
                FROM core.fact_expenses
            """,
        },
        {
            "name": "cash_transaction_amount",
            "source_sql": """
                SELECT COALESCE(
                    SUM(amount),
                    0
                )
                FROM (
                    SELECT DISTINCT ON (transaction_id)
                        transaction_id,
                        amount
                    FROM staging.stg_cash_transactions
                    WHERE record_status = 'pending'
                    ORDER BY
                        transaction_id,
                        ingested_at DESC,
                        stg_cash_transaction_id DESC
                ) AS latest_transactions
            """,
            "warehouse_sql": """
                SELECT COALESCE(
                    SUM(amount),
                    0
                )
                FROM core.fact_cash_transactions
            """,
        },
    )

    def __init__(
        self,
        session: Session,
    ) -> None:
        self.session = session

    def validate_all(
        self,
    ) -> list[ReconciliationResult]:
        """Run all reconciliation checks."""

        return [
            self.validate_metric(metric)
            for metric in self.RECONCILIATIONS
        ]

    def validate_metric(
        self,
        metric: dict[str, str],
    ) -> ReconciliationResult:
        """Validate one financial metric."""

        source_value = self._execute_decimal(
            metric["source_sql"]
        )

        warehouse_value = self._execute_decimal(
            metric["warehouse_sql"]
        )

        return ReconciliationResult(
            metric_name=metric["name"],
            source_value=source_value,
            warehouse_value=warehouse_value,
        )

    def _execute_decimal(
        self,
        sql: str,
    ) -> Decimal:
        """Execute a query and return a Decimal."""

        result = self.session.execute(
            text(sql)
        )

        value = result.scalar_one()

        return Decimal(str(value))