"""
Time grain resolution.

Every analytics.* view carries its own "primary date" column (each
view joins core.dim_date and aliases the date differently — e.g.
`sale_date` on analytics.v_sales, `expense_date` on
analytics.v_expenses). This module is the single place that maps a
source view to that column, and maps an abstract TimeGrain to the
Postgres date_trunc() unit used to bucket it.

date_trunc() is used (rather than grouping on the pre-computed
year/quarter/month columns already present on the views) because it
produces a single, sortable, gap-aware bucket column regardless of
grain, which is what a query builder needs for GROUP BY / ORDER BY.
"""

from __future__ import annotations

from etl.analytics.metrics.definitions import TimeGrain


class UnknownSourceViewError(Exception):
    """Raised when a source_view has no registered primary date column."""


# source_view -> the column on that view holding the row's business date.
VIEW_PRIMARY_DATE_COLUMN: dict[str, str] = {
    "analytics.v_orders": "order_date",
    "analytics.v_sales": "sale_date",
    "analytics.v_payments": "payment_date",
    "analytics.v_returns": "return_date",
    "analytics.v_return_items": "return_date",
    "analytics.v_purchases": "purchase_date",
    "analytics.v_cash_transactions": "transaction_date",
    "analytics.v_expenses": "expense_date",
    "analytics.v_partner_capital": "transaction_date",
    "analytics.v_stock_movements": "movement_date",
    "analytics.v_daily_business_summary": "business_date",
}

# TimeGrain -> the unit argument passed to Postgres date_trunc().
_GRAIN_TO_DATE_TRUNC_UNIT: dict[TimeGrain, str] = {
    "daily": "day",
    "weekly": "week",
    "monthly": "month",
    "quarterly": "quarter",
    "yearly": "year",
}

# Alias used for the bucketed date column in generated SQL.
PERIOD_ALIAS = "period"


def primary_date_column(source_view: str) -> str:
    """Return the primary date column name for a source view.

    Raises:
        UnknownSourceViewError: If the view isn't registered above.
    """

    try:
        return VIEW_PRIMARY_DATE_COLUMN[source_view]
    except KeyError as exc:
        raise UnknownSourceViewError(
            f"No primary date column registered for source_view "
            f"'{source_view}'. Add it to VIEW_PRIMARY_DATE_COLUMN in "
            f"time_grains.py."
        ) from exc


def date_trunc_expression(source_view: str, grain: TimeGrain) -> str:
    """Build the `date_trunc('unit', date_column)` expression used to
    bucket rows from `source_view` at the requested `grain`."""

    if grain not in _GRAIN_TO_DATE_TRUNC_UNIT:
        raise ValueError(f"Unsupported time grain: {grain!r}")

    unit = _GRAIN_TO_DATE_TRUNC_UNIT[grain]
    column = primary_date_column(source_view)
    return f"date_trunc('{unit}', {column})"