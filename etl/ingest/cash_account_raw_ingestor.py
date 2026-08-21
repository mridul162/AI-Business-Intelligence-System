"""
Raw ingestion logic for cash account data.

Reads Cash_Accounts.csv and ingests previously unseen records into
raw.cash_accounts using source_row_hash for duplicate detection.
"""

from __future__ import annotations

import csv
import hashlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from etl.utils.ingestion_batch import (
    create_ingestion_batch,
    mark_batch_completed,
    mark_batch_failed,
)

logger = logging.getLogger(__name__)


class CashAccountRawIngestor:
    """Ingest cash account CSV records into raw.cash_accounts."""

    SOURCE_SYSTEM = "HBMS"
    SOURCE_TYPE = "csv"

    INSERT_SQL = text(
        """
        INSERT INTO raw.cash_accounts (
            ingestion_batch_id,
            source_row_number,
            source_row_hash,
            cash_account_id,
            account_name,
            account_type,
            owner_id,
            active,
            total_in,
            total_out,
            current_balance
        )
        VALUES (
            :ingestion_batch_id,
            :source_row_number,
            :source_row_hash,
            :cash_account_id,
            :account_name,
            :account_type,
            :owner_id,
            :active,
            :total_in,
            :total_out,
            :current_balance
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
    def _clean_value(value: str | None) -> str | None:
        """Normalize CSV values."""
        if value is None:
            return None

        value = value.strip()
        return value or None

    @staticmethod
    def _generate_row_hash(
        row: dict[str, Any],
    ) -> str:
        """Generate a deterministic hash for a source row."""

        normalized_row = "|".join(
            f"{key}={row.get(key, '')}"
            for key in sorted(row.keys())
        )

        return hashlib.sha256(
            normalized_row.encode("utf-8")
        ).hexdigest()

    def _record_exists(
        self,
        source_row_hash: str,
    ) -> bool:
        """Check whether an identical source record already exists."""

        result = self.session.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM raw.cash_accounts
                    WHERE source_row_hash = :source_row_hash
                );
                """
            ),
            {
                "source_row_hash": source_row_hash,
            },
        )

        return bool(result.scalar())

    def ingest(self) -> dict[str, Any]:
        """Read and ingest previously unseen cash account records."""

        if not self.csv_path.exists():
            raise FileNotFoundError(
                f"CSV file not found: {self.csv_path}"
            )

        batch_id = create_ingestion_batch(
            self.session,
            source_system=self.SOURCE_SYSTEM,
            source_type=self.SOURCE_TYPE,
            source_reference=str(self.csv_path),
        )

        records_received = 0
        records_loaded = 0
        records_rejected = 0

        logger.info(
            "Started cash account raw ingestion. Batch ID: %s",
            batch_id,
        )

        try:
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
                        cash_account_record = {
                            "cash_account_id": self._clean_value(
                                row.get("Cash_Account_ID")
                            ),
                            "account_name": self._clean_value(
                                row.get("Account_Name")
                            ),
                            "account_type": self._clean_value(
                                row.get("Account_Type")
                            ),
                            "owner_id": self._clean_value(
                                row.get("Owner_ID")
                            ),
                            "active": self._clean_value(
                                row.get("Active")
                            ),
                            "total_in": self._clean_value(
                                row.get("Total_In")
                            ),
                            "total_out": self._clean_value(
                                row.get("Total_Out")
                            ),
                            "current_balance": self._clean_value(
                                row.get("Current_Balance")
                            ),
                        }

                        source_row_hash = self._generate_row_hash(
                            cash_account_record
                        )

                        if self._record_exists(source_row_hash):
                            continue

                        payload = {
                            "ingestion_batch_id": batch_id,
                            "source_row_number": row_number,
                            "source_row_hash": source_row_hash,
                            **cash_account_record,
                        }

                        self.session.execute(
                            self.INSERT_SQL,
                            payload,
                        )

                        records_loaded += 1

                    except Exception:
                        records_rejected += 1

                        logger.exception(
                            "Failed to ingest cash account row %s.",
                            row_number,
                        )

            mark_batch_completed(
                self.session,
                ingestion_batch_id=batch_id,
                records_received=records_received,
                records_loaded=records_loaded,
                records_rejected=records_rejected,
            )

            logger.info(
                "Cash account raw ingestion completed. "
                "Batch ID: %s, Received: %s, Loaded: %s, "
                "Rejected: %s",
                batch_id,
                records_received,
                records_loaded,
                records_rejected,
            )

            return {
                "ingestion_batch_id": batch_id,
                "records_received": records_received,
                "records_loaded": records_loaded,
                "records_rejected": records_rejected,
            }

        except Exception as exc:
            logger.exception(
                "Cash account raw ingestion failed. "
                "Batch ID: %s",
                batch_id,
            )

            mark_batch_failed(
                self.session,
                ingestion_batch_id=batch_id,
                error_message=str(exc),
                records_received=records_received,
                records_loaded=records_loaded,
                records_rejected=records_rejected,
            )

            raise