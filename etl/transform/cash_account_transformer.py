"""
Transformation logic for cash account records.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from etl.transform.base import BaseTransformer


class CashAccountTransformer(BaseTransformer):
    """Transform raw cash account records into staging format."""

    @staticmethod
    def _clean_text(
        value: Any,
    ) -> str | None:
        if value is None:
            return None

        value = str(value).strip()
        return value or None

    @staticmethod
    def _to_decimal(
        value: Any,
    ) -> Decimal | None:
        if value is None:
            return None

        value = str(value).strip()

        if not value:
            return None

        try:
            return Decimal(value.replace(",", ""))
        except (
            InvalidOperation,
            ValueError,
        ) as exc:
            raise ValueError(
                f"Invalid decimal value: {value!r}"
            ) from exc

    @staticmethod
    def _to_boolean(
        value: Any,
    ) -> bool | None:
        if value is None:
            return None

        normalized = str(value).strip().lower()

        if not normalized:
            return None

        true_values = {
            "true",
            "1",
            "yes",
            "y",
            "active",
        }

        false_values = {
            "false",
            "0",
            "no",
            "n",
            "inactive",
        }

        if normalized in true_values:
            return True

        if normalized in false_values:
            return False

        raise ValueError(
            f"Invalid boolean value: {value!r}"
        )

    def transform(
        self,
        data: dict[str, Any],
        *args,
        **kwargs,
    ) -> dict[str, Any]:
        """Transform one raw cash account record."""

        return {
            "cash_account_id": self._clean_text(
                data.get("cash_account_id")
            ),
            "account_name": self._clean_text(
                data.get("account_name")
            ),
            "account_type": self._clean_text(
                data.get("account_type")
            ),
            "owner_id": self._clean_text(
                data.get("owner_id")
            ),
            "active": self._to_boolean(
                data.get("active")
            ),
            "total_in": self._to_decimal(
                data.get("total_in")
            ),
            "total_out": self._to_decimal(
                data.get("total_out")
            ),
            "current_balance": self._to_decimal(
                data.get("current_balance")
            ),
            "source_system": "HBMS",
            "source_table": "cash_accounts",
            "source_row_identifier": str(
                data.get("raw_id")
            ),
            "ingestion_batch_id": data.get(
                "ingestion_batch_id"
            ),
            "ingested_at": data.get(
                "ingested_at"
            ) or datetime.now(),
            "source_hash": data.get(
                "source_row_hash"
            ),
            "record_status": "pending",
            "validation_error": None,
        }