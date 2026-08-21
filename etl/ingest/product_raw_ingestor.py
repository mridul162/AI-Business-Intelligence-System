"""
Raw ingestion logic for product data.

Reads Products.csv and loads the source data into raw.products without
applying business transformations. Type conversion and business validation
are handled later by the Product ETL pipeline.
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

from database.connection import session_scope
from etl.utils.ingestion_batch import (
    create_ingestion_batch,
    mark_batch_completed,
    mark_batch_failed,
)


logger = logging.getLogger(__name__)


@dataclass
class ProductRawIngestionResult:
    """Summary of a product raw ingestion run."""

    ingestion_batch_id: str
    records_received: int
    records_loaded: int
    records_rejected: int


class ProductRawIngestor:
    """
    Ingest product records from a CSV export into raw.products.

    The raw layer preserves source values without business transformations.
    All source columns are stored as text, matching the raw.products schema.
    """

    SOURCE_SYSTEM = "HBMS"
    SOURCE_TYPE = "csv"

    INSERT_SQL = text(
        """
        INSERT INTO raw.products (
            ingestion_batch_id,
            source_row_number,
            source_row_hash,
            product_id,
            product_name,
            category,
            unit,
            selling_price,
            cost_price,
            opening_stock,
            reorder_level,
            active
        )
        VALUES (
            :ingestion_batch_id,
            :source_row_number,
            :source_row_hash,
            :product_id,
            :product_name,
            :category,
            :unit,
            :selling_price,
            :cost_price,
            :opening_stock,
            :reorder_level,
            :active
        );
        """
    )

    INSERT_ERROR_SQL = text(
        """
        INSERT INTO raw.ingestion_errors (
            ingestion_batch_id,
            source_table,
            source_row_identifier,
            error_type,
            error_message,
            raw_payload
        )
        VALUES (
            :ingestion_batch_id,
            :source_table,
            :source_row_identifier,
            :error_type,
            :error_message,
            CAST(:raw_payload AS jsonb)
        );
        """
    )

    def __init__(
        self,
        csv_path: str | Path,
    ) -> None:
        """
        Initialize the raw ingestor.

        Args:
            csv_path: Path to the Products.csv source export.
        """
        self.csv_path = Path(csv_path)

    @staticmethod
    def _clean_raw_value(value: Any) -> str | None:
        """
        Normalize empty CSV values to None.

        No business transformation is performed here.
        """
        if value is None:
            return None

        value = str(value).strip()

        return value if value else None

    @staticmethod
    def _generate_row_hash(
        row: dict[str, Any],
    ) -> str:
        """
        Generate a deterministic SHA-256 hash for a source row.
        """
        normalized_row = {
            key: ProductRawIngestor._clean_raw_value(value)
            for key, value in sorted(row.items())
        }

        serialized_row = json.dumps(
            normalized_row,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )

        return hashlib.sha256(
            serialized_row.encode("utf-8")
        ).hexdigest()

    def _log_ingestion_error(
        self,
        session: Session,
        *,
        ingestion_batch_id: str,
        source_row_identifier: str,
        error_message: str,
        raw_payload: dict[str, Any],
    ) -> None:
        """Persist a row-level ingestion error."""

        session.execute(
            self.INSERT_ERROR_SQL,
            {
                "ingestion_batch_id": ingestion_batch_id,
                "source_table": "products",
                "source_row_identifier": source_row_identifier,
                "error_type": "ingestion_error",
                "error_message": error_message,
                "raw_payload": json.dumps(
                    raw_payload,
                    default=str,
                    ensure_ascii=False,
                ),
            },
        )

    def ingest(self) -> ProductRawIngestionResult:
        """
        Execute product CSV ingestion into raw.products.

        Returns:
            ProductRawIngestionResult containing batch and record counts.
        """
        if not self.csv_path.exists():
            raise FileNotFoundError(
                f"Products CSV file not found: {self.csv_path}"
            )

        batch_id: str | None = None
        records_received = 0
        records_loaded = 0
        records_rejected = 0

        try:
            # ---------------------------------------------
            # 1. Create ingestion batch
            # ---------------------------------------------
            with session_scope() as session:
                batch_id = str(
                    create_ingestion_batch(
                        session,
                        source_system=self.SOURCE_SYSTEM,
                        source_type=self.SOURCE_TYPE,
                        source_reference=str(
                            self.csv_path.resolve()
                        ),
                    )
                )

            logger.info(
                "Started product raw ingestion. Batch ID: %s",
                batch_id,
            )

            # ---------------------------------------------
            # 2. Read CSV and ingest rows
            # ---------------------------------------------
            with session_scope() as session:
                with self.csv_path.open(
                    mode="r",
                    encoding="utf-8-sig",
                    newline="",
                ) as csv_file:

                    reader = csv.DictReader(csv_file)

                    required_columns = {
                        "Product_ID",
                        "Product_Name",
                        "Category",
                        "Unit",
                        "Selling_Price",
                        "Cost_Price",
                        "Opening_Stock",
                        "Reorder_Level",
                        "Active",
                    }

                    actual_columns = set(
                        reader.fieldnames or []
                    )

                    missing_columns = (
                        required_columns - actual_columns
                    )

                    if missing_columns:
                        raise ValueError(
                            "Products.csv is missing required columns: "
                            f"{sorted(missing_columns)}"
                        )

                    for source_row_number, row in enumerate(
                        reader,
                        start=2,
                    ):
                        records_received += 1

                        try:
                            source_row_hash = (
                                self._generate_row_hash(row)
                            )

                            payload = {
                                "ingestion_batch_id": batch_id,
                                "source_row_number": (
                                    source_row_number
                                ),
                                "source_row_hash": source_row_hash,
                                "product_id": (
                                    self._clean_raw_value(
                                        row.get("Product_ID")
                                    )
                                ),
                                "product_name": (
                                    self._clean_raw_value(
                                        row.get("Product_Name")
                                    )
                                ),
                                "category": (
                                    self._clean_raw_value(
                                        row.get("Category")
                                    )
                                ),
                                "unit": (
                                    self._clean_raw_value(
                                        row.get("Unit")
                                    )
                                ),
                                "selling_price": (
                                    self._clean_raw_value(
                                        row.get("Selling_Price")
                                    )
                                ),
                                "cost_price": (
                                    self._clean_raw_value(
                                        row.get("Cost_Price")
                                    )
                                ),
                                "opening_stock": (
                                    self._clean_raw_value(
                                        row.get("Opening_Stock")
                                    )
                                ),
                                "reorder_level": (
                                    self._clean_raw_value(
                                        row.get("Reorder_Level")
                                    )
                                ),
                                "active": (
                                    self._clean_raw_value(
                                        row.get("Active")
                                    )
                                ),
                            }

                            session.execute(
                                self.INSERT_SQL,
                                payload,
                            )

                            records_loaded += 1

                        except Exception as exc:
                            records_rejected += 1

                            logger.exception(
                                "Failed to ingest product row %s.",
                                source_row_number,
                            )

                            self._log_ingestion_error(
                                session,
                                ingestion_batch_id=batch_id,
                                source_row_identifier=str(
                                    source_row_number
                                ),
                                error_message=str(exc),
                                raw_payload=row,
                            )

            # ---------------------------------------------
            # 3. Mark batch completed
            # ---------------------------------------------
            with session_scope() as session:
                mark_batch_completed(
                    session,
                    ingestion_batch_id=batch_id, # type: ignore
                    records_received=records_received,
                    records_loaded=records_loaded,
                    records_rejected=records_rejected,
                )

            logger.info(
                "Product raw ingestion completed. "
                "Batch ID: %s, Received: %s, Loaded: %s, Rejected: %s",
                batch_id,
                records_received,
                records_loaded,
                records_rejected,
            )

            return ProductRawIngestionResult(
                ingestion_batch_id=batch_id,
                records_received=records_received,
                records_loaded=records_loaded,
                records_rejected=records_rejected,
            )

        except Exception as exc:
            logger.exception(
                "Product raw ingestion failed. Batch ID: %s",
                batch_id,
            )

            if batch_id is not None:
                try:
                    with session_scope() as session:
                        mark_batch_failed(
                            session,
                            ingestion_batch_id=batch_id, # type: ignore
                            error_message=str(exc),
                            records_received=records_received,
                            records_loaded=records_loaded,
                            records_rejected=records_rejected,
                        )
                except Exception:
                    logger.exception(
                        "Failed to mark product ingestion batch as failed. "
                        "Batch ID: %s",
                        batch_id,
                    )

            raise