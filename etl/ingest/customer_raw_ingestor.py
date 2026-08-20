"""
Customer raw data ingestor.

Reads exported customer data from CSV and loads it into raw.customers.

Flow:
    data/raw_exports/Customers.csv
        ↓
    CustomerRawIngestor
        ↓
    raw.ingestion_batches
        ↓
    raw.customers

The raw layer preserves source values as received. Business transformations
and type conversions are handled later in the ETL pipeline.
"""

from __future__ import annotations

import csv
import hashlib
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


@dataclass
class CustomerRawIngestionResult:
    """Summary of a customer raw ingestion run."""

    ingestion_batch_id: str
    records_received: int
    records_loaded: int
    records_rejected: int


class CustomerRawIngestor:
    """
    Ingest customer records from a CSV export into raw.customers.

    This component performs ingestion only.

    It does NOT:
        - convert source values into typed values
        - calculate business metrics
        - validate business rules
        - transform customer records for staging

    Those responsibilities belong to the later ETL stages.
    """

    SOURCE_SYSTEM = "HBMS"
    SOURCE_TYPE = "csv"

    def __init__(
        self,
        session: Session,
        csv_path: str | Path,
    ) -> None:
        self.session = session
        self.csv_path = Path(csv_path)

    def ingest(self) -> CustomerRawIngestionResult:
        """
        Read the customer CSV and ingest records into raw.customers.

        Returns:
            CustomerRawIngestionResult with batch and record statistics.

        Raises:
            FileNotFoundError:
                If the CSV file does not exist.

            Exception:
                If ingestion fails. The ingestion batch is marked as failed.
        """

        if not self.csv_path.exists():
            raise FileNotFoundError(
                f"Customer CSV file not found: {self.csv_path}"
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
            "Started customer raw ingestion. Batch ID: %s",
            batch_id,
        )

        try:
            with self.csv_path.open(
                mode="r",
                encoding="utf-8-sig",
                newline="",
            ) as file:
                reader = csv.DictReader(file)

                if reader.fieldnames is None:
                    raise ValueError(
                        "Customer CSV does not contain a header row."
                    )

                for row_number, row in enumerate(reader, start=2):
                    records_received += 1

                    try:
                        source_row_hash = self._generate_row_hash(row)

                        self._insert_customer(
                            batch_id=batch_id,
                            source_row_number=row_number,
                            source_row_hash=source_row_hash,
                            row=row,
                        )

                        records_loaded += 1

                    except Exception as exc:
                        records_rejected += 1

                        logger.exception(
                            "Failed to ingest customer row %s: %s",
                            row_number,
                            exc,
                        )

            mark_batch_completed(
                self.session,
                ingestion_batch_id=batch_id,
                records_received=records_received,
                records_loaded=records_loaded,
                records_rejected=records_rejected,
            )

            logger.info(
                "Customer raw ingestion completed. "
                "Batch ID: %s, Received: %s, Loaded: %s, Rejected: %s",
                batch_id,
                records_received,
                records_loaded,
                records_rejected,
            )

            return CustomerRawIngestionResult(
                ingestion_batch_id=str(batch_id),
                records_received=records_received,
                records_loaded=records_loaded,
                records_rejected=records_rejected,
            )

        except Exception as exc:
            logger.exception(
                "Customer raw ingestion failed. Batch ID: %s",
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

    def _insert_customer(
        self,
        batch_id: Any,
        source_row_number: int,
        source_row_hash: str,
        row: dict[str, str | None],
    ) -> None:
        """Insert one source customer row into raw.customers."""

        query = text(
            """
            INSERT INTO raw.customers (
                ingestion_batch_id,
                source_row_number,
                source_row_hash,
                customer_id,
                customer_name,
                contact,
                address,
                first_order_date,
                last_order_date,
                total_orders,
                total_spent,
                total_paid,
                total_due,
                status
            )
            VALUES (
                :ingestion_batch_id,
                :source_row_number,
                :source_row_hash,
                :customer_id,
                :customer_name,
                :contact,
                :address,
                :first_order_date,
                :last_order_date,
                :total_orders,
                :total_spent,
                :total_paid,
                :total_due,
                :status
            )
            """
        )

        self.session.execute(
            query,
            {
                "ingestion_batch_id": batch_id,
                "source_row_number": source_row_number,
                "source_row_hash": source_row_hash,
                "customer_id": self._get_value(row, "Customer_ID"),
                "customer_name": self._get_value(row, "Customer_Name"),
                "contact": self._get_value(row, "Contact"),
                "address": self._get_value(row, "Address"),
                "first_order_date": self._get_value(
                    row,
                    "First_Order_Date",
                ),
                "last_order_date": self._get_value(
                    row,
                    "Last_Order_Date",
                ),
                "total_orders": self._get_value(row, "Total_Orders"),
                "total_spent": self._get_value(row, "Total_Spent"),
                "total_paid": self._get_value(row, "Total_Paid"),
                "total_due": self._get_value(row, "Total_Due"),
                "status": self._get_value(row, "Status"),
            },
        )

    @staticmethod
    def _get_value(
        row: dict[str, str | None],
        column_name: str,
    ) -> str | None:
        """
        Return a cleaned source value.

        Empty strings are converted to None, but values are otherwise
        preserved without type transformation.
        """

        value = row.get(column_name)

        if value is None:
            return None

        value = value.strip()

        return value if value else None

    @staticmethod
    def _generate_row_hash(
        row: dict[str, str | None],
    ) -> str:
        """
        Generate a deterministic SHA-256 hash for the source row.

        This hash can later support change detection and idempotent ingestion.
        """

        normalized_values = [
            f"{key}={row.get(key, '') or ''}"
            for key in sorted(row.keys())
        ]

        row_content = "|".join(normalized_values)

        return hashlib.sha256(
            row_content.encode("utf-8")
        ).hexdigest()