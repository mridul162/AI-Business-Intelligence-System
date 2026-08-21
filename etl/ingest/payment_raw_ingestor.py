"""
Raw ingestion logic for payment records.

Reads Payments.csv and stores source records in raw.payments.
"""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from etl.utils.ingestion_batch import (
    create_ingestion_batch,
    mark_batch_completed,
    mark_batch_failed,
)


class PaymentRawIngestor:
    """
    Ingest payment records from a CSV file into raw.payments.
    """

    SOURCE_SYSTEM = "HBMS"
    SOURCE_TYPE = "csv"

    INSERT_SQL = text(
        """
        INSERT INTO raw.payments (
            ingestion_batch_id,
            source_row_number,
            source_row_hash,
            payment_id,
            payment_date,
            order_id,
            customer_id,
            amount,
            payment_method,
            cash_account_id,
            collected_by,
            cash_transaction_id,
            notes,
            created_at
        )
        SELECT
            :ingestion_batch_id,
            :source_row_number,
            :source_row_hash,
            :payment_id,
            :payment_date,
            :order_id,
            :customer_id,
            :amount,
            :payment_method,
            :cash_account_id,
            :collected_by,
            NULL,
            :notes,
            :created_at
        WHERE NOT EXISTS (
            SELECT 1
            FROM raw.payments
            WHERE source_row_hash = :source_row_hash
        );
        """
    )

    def __init__(
        self,
        session: Session,
        csv_path: str | Path,
    ) -> None:
        self.session = session
        self.csv_path = Path(csv_path)

    @staticmethod
    def _clean_value(value: Any) -> str | None:
        """Normalize CSV values."""
        if value is None:
            return None

        value = str(value).strip()
        return value or None

    @staticmethod
    def _calculate_row_hash(
        row: dict[str, Any],
    ) -> str:
        """Create a deterministic hash for a source row."""

        normalized_values = [
            str(value).strip()
            if value is not None
            else ""
            for value in row.values()
        ]

        raw_value = "|".join(normalized_values)

        return hashlib.sha256(
            raw_value.encode("utf-8")
        ).hexdigest()

    def ingest(self) -> dict[str, Any]:
        """
        Ingest Payments.csv into raw.payments.

        Returns ingestion batch and record statistics.
        """

        if not self.csv_path.exists():
            raise FileNotFoundError(
                f"Payments CSV file not found: {self.csv_path}"
            )

        batch_id = None
        records_received = 0
        records_loaded = 0
        records_rejected = 0

        try:
            batch_id = create_ingestion_batch(
                self.session,
                source_system=self.SOURCE_SYSTEM,
                source_type=self.SOURCE_TYPE,
                source_reference=str(self.csv_path.resolve()),
            )

            with self.csv_path.open(
                mode="r",
                encoding="utf-8-sig",
                newline="",
            ) as file:
                reader = csv.DictReader(file)

                for row_number, row in enumerate(
                    reader,
                    start=2,
                ):
                    records_received += 1

                    try:
                        source_row_hash = self._calculate_row_hash(row)

                        payload = {
                            "ingestion_batch_id": batch_id,
                            "source_row_number": row_number,
                            "source_row_hash": source_row_hash,
                            "payment_id": self._clean_value(
                                row.get("Payment_ID")
                            ),
                            "payment_date": self._clean_value(
                                row.get("Payment_Date")
                            ),
                            "order_id": self._clean_value(
                                row.get("Order_ID")
                            ),
                            "customer_id": self._clean_value(
                                row.get("Customer_ID")
                            ),
                            "amount": self._clean_value(
                                row.get("Amount")
                            ),
                            "payment_method": self._clean_value(
                                row.get("Payment_Method")
                            ),
                            "cash_account_id": self._clean_value(
                                row.get("Cash_Account_ID")
                            ),
                            "collected_by": self._clean_value(
                                row.get("Collected_By")
                            ),
                            "notes": self._clean_value(
                                row.get("Notes")
                            ),
                            "created_at": self._clean_value(
                                row.get("Created_At")
                            ),
                        }

                        result = self.session.execute(
                            self.INSERT_SQL,
                            payload,
                        )

                        if result.rowcount > 0:
                            records_loaded += 1

                    except Exception:
                        records_rejected += 1
                        raise

            mark_batch_completed(
                self.session,
                ingestion_batch_id=batch_id,
                records_received=records_received,
                records_loaded=records_loaded,
                records_rejected=records_rejected,
            )

            return {
                "ingestion_batch_id": str(batch_id),
                "records_received": records_received,
                "records_loaded": records_loaded,
                "records_rejected": records_rejected,
            }

        except Exception as exc:
            if batch_id is not None:
                mark_batch_failed(
                    self.session,
                    ingestion_batch_id=batch_id,
                    error_message=str(exc),
                    records_received=records_received,
                    records_loaded=records_loaded,
                    records_rejected=records_rejected,
                )

            raise