"""
Validation logic for warehouse fact tables.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass
class FactValidationResult:
    """Result of one fact table validation."""

    fact_name: str
    expected_count: int
    actual_count: int
    duplicate_count: int

    @property
    def is_valid(self) -> bool:
        """Return whether the fact validation passed."""

        return (
            self.expected_count == self.actual_count
            and self.duplicate_count == 0
        )


class FactValidator:
    """Validate warehouse fact tables."""

    FACTS = (
        {
            "name": "fact_orders",
            "expected_sql": """
                SELECT COUNT(DISTINCT order_id)
                FROM staging.stg_orders
                WHERE record_status = 'pending'
                  AND order_id IS NOT NULL
            """,
            "actual_sql": """
                SELECT COUNT(*)
                FROM core.fact_orders
            """,
            "duplicate_sql": """
                SELECT COUNT(*)
                FROM (
                    SELECT order_id
                    FROM core.fact_orders
                    GROUP BY order_id
                    HAVING COUNT(*) > 1
                ) AS duplicates
            """,
        },
        {
            "name": "fact_sales",
            "expected_sql": """
                SELECT COUNT(DISTINCT order_item_id)
                FROM staging.stg_order_items
                WHERE record_status = 'pending'
                  AND order_item_id IS NOT NULL
            """,
            "actual_sql": """
                SELECT COUNT(*)
                FROM core.fact_sales
            """,
            "duplicate_sql": """
                SELECT COUNT(*)
                FROM (
                    SELECT order_item_id
                    FROM core.fact_sales
                    GROUP BY order_item_id
                    HAVING COUNT(*) > 1
                ) AS duplicates
            """,
        },
        {
            "name": "fact_payments",
            "expected_sql": """
                SELECT COUNT(DISTINCT payment_id)
                FROM staging.stg_payments
                WHERE record_status = 'pending'
                  AND payment_id IS NOT NULL
            """,
            "actual_sql": """
                SELECT COUNT(*)
                FROM core.fact_payments
            """,
            "duplicate_sql": """
                SELECT COUNT(*)
                FROM (
                    SELECT payment_id
                    FROM core.fact_payments
                    GROUP BY payment_id
                    HAVING COUNT(*) > 1
                ) AS duplicates
            """,
        },
        {
            "name": "fact_returns",
            "expected_sql": """
                SELECT COUNT(DISTINCT return_id)
                FROM staging.stg_returns
                WHERE record_status = 'pending'
                  AND return_id IS NOT NULL
            """,
            "actual_sql": """
                SELECT COUNT(*)
                FROM core.fact_returns
            """,
            "duplicate_sql": """
                SELECT COUNT(*)
                FROM (
                    SELECT return_id
                    FROM core.fact_returns
                    GROUP BY return_id
                    HAVING COUNT(*) > 1
                ) AS duplicates
            """,
        },
        {
            "name": "fact_return_items",
            "expected_sql": """
                SELECT COUNT(DISTINCT return_item_id)
                FROM staging.stg_return_items
                WHERE record_status = 'pending'
                  AND return_item_id IS NOT NULL
            """,
            "actual_sql": """
                SELECT COUNT(*)
                FROM core.fact_return_items
            """,
            "duplicate_sql": """
                SELECT COUNT(*)
                FROM (
                    SELECT return_item_id
                    FROM core.fact_return_items
                    GROUP BY return_item_id
                    HAVING COUNT(*) > 1
                ) AS duplicates
            """,
        },
        {
            "name": "fact_purchases",
            "expected_sql": """
                SELECT COUNT(DISTINCT purchase_item_id)
                FROM staging.stg_purchase_items
                WHERE record_status = 'pending'
                  AND purchase_item_id IS NOT NULL
            """,
            "actual_sql": """
                SELECT COUNT(*)
                FROM core.fact_purchases
            """,
            "duplicate_sql": """
                SELECT COUNT(*)
                FROM (
                    SELECT purchase_item_id
                    FROM core.fact_purchases
                    GROUP BY purchase_item_id
                    HAVING COUNT(*) > 1
                ) AS duplicates
            """,
        },
        {
            "name": "fact_cash_transactions",
            "expected_sql": """
                SELECT COUNT(DISTINCT transaction_id)
                FROM staging.stg_cash_transactions
                WHERE record_status = 'pending'
                  AND transaction_id IS NOT NULL
            """,
            "actual_sql": """
                SELECT COUNT(*)
                FROM core.fact_cash_transactions
            """,
            "duplicate_sql": """
                SELECT COUNT(*)
                FROM (
                    SELECT transaction_id
                    FROM core.fact_cash_transactions
                    GROUP BY transaction_id
                    HAVING COUNT(*) > 1
                ) AS duplicates
            """,
        },
        {
            "name": "fact_expenses",
            "expected_sql": """
                SELECT COUNT(DISTINCT expense_id)
                FROM staging.stg_expenses
                WHERE record_status = 'pending'
                  AND expense_id IS NOT NULL
            """,
            "actual_sql": """
                SELECT COUNT(*)
                FROM core.fact_expenses
            """,
            "duplicate_sql": """
                SELECT COUNT(*)
                FROM (
                    SELECT expense_id
                    FROM core.fact_expenses
                    GROUP BY expense_id
                    HAVING COUNT(*) > 1
                ) AS duplicates
            """,
        },
        {
            "name": "fact_partner_capital",
            "expected_sql": """
                SELECT COUNT(DISTINCT capital_transaction_id)
                FROM staging.stg_partner_capital
                WHERE record_status = 'pending'
                  AND capital_transaction_id IS NOT NULL
            """,
            "actual_sql": """
                SELECT COUNT(*)
                FROM core.fact_partner_capital
            """,
            "duplicate_sql": """
                SELECT COUNT(*)
                FROM (
                    SELECT capital_transaction_id
                    FROM core.fact_partner_capital
                    GROUP BY capital_transaction_id
                    HAVING COUNT(*) > 1
                ) AS duplicates
            """,
        },
        {
            "name": "fact_stock_movements",
            "expected_sql": """
                SELECT COUNT(DISTINCT movement_id)
                FROM staging.stg_stock_movements
                WHERE record_status = 'pending'
                  AND movement_id IS NOT NULL
            """,
            "actual_sql": """
                SELECT COUNT(*)
                FROM core.fact_stock_movements
            """,
            "duplicate_sql": """
                SELECT COUNT(*)
                FROM (
                    SELECT movement_id
                    FROM core.fact_stock_movements
                    GROUP BY movement_id
                    HAVING COUNT(*) > 1
                ) AS duplicates
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
    ) -> list[FactValidationResult]:
        """Validate all warehouse facts."""

        return [
            self.validate_fact(fact)
            for fact in self.FACTS
        ]

    def validate_fact(
        self,
        fact: dict[str, str],
    ) -> FactValidationResult:
        """Validate one fact table."""

        expected_count = self._execute_scalar(
            fact["expected_sql"]
        )

        actual_count = self._execute_scalar(
            fact["actual_sql"]
        )

        duplicate_count = self._execute_scalar(
            fact["duplicate_sql"]
        )

        return FactValidationResult(
            fact_name=fact["name"],
            expected_count=expected_count,
            actual_count=actual_count,
            duplicate_count=duplicate_count,
        )

    def _execute_scalar(
        self,
        sql: str,
    ) -> int:
        """Execute SQL returning one integer."""

        result = self.session.execute(
            text(sql)
        )

        return result.scalar_one()