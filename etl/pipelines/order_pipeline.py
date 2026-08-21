"""
Order ETL pipeline.

Pipeline flow:

    raw.orders
        ↓
    OrderExtractor
        ↓
    OrderTransformer
        ↓
    OrderValidator
        ↓
    OrderLoader
        ↓
    staging.stg_orders

Each pipeline run is tracked through raw.ingestion_batches.
Invalid records are stored in raw.ingestion_errors.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text

from database.connection import session_scope

from etl.extract.order_extractor import OrderExtractor
from etl.load.order_loader import OrderLoader
from etl.transform.order_transformer import OrderTransformer
from etl.utils.ingestion_batch import (
    create_ingestion_batch,
    mark_batch_completed,
    mark_batch_failed,
)
from etl.validators.order_validator import OrderValidator


logger = logging.getLogger(__name__)


@dataclass
class OrderPipelineResult:
    """Summary of an order ETL pipeline run."""

    ingestion_batch_id: str
    records_received: int
    records_loaded: int
    records_rejected: int


class OrderPipeline:
    """Orchestrate the complete order ETL pipeline."""

    SOURCE_SYSTEM = "HBMS"
    SOURCE_TYPE = "postgresql"
    SOURCE_REFERENCE = "raw.orders"
    SOURCE_TABLE = "orders"

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

    def __init__(self) -> None:
        self.extractor = OrderExtractor()
        self.transformer = OrderTransformer()
        self.validator = OrderValidator()

    def run(self) -> OrderPipelineResult:
        """Execute the complete order ETL pipeline."""

        batch_id = None
        records_received = 0
        records_loaded = 0
        records_rejected = 0

        try:
            # ---------------------------------------------
            # 1. Create ETL ingestion batch
            # ---------------------------------------------
            with session_scope() as session:
                batch_id = create_ingestion_batch(
                    session,
                    source_system=self.SOURCE_SYSTEM,
                    source_type=self.SOURCE_TYPE,
                    source_reference=self.SOURCE_REFERENCE,
                )

            logger.info(
                "Created order ETL batch: %s",
                batch_id,
            )

            # ---------------------------------------------
            # 2. Extract
            # ---------------------------------------------
            with session_scope() as session:
                extracted_records = self.extractor.extract(
                    session=session,
                )

            records_received = len(extracted_records)

            logger.info(
                "Order extraction completed. "
                "Records received: %s",
                records_received,
            )

            valid_records: list[dict[str, Any]] = []

            # ---------------------------------------------
            # 3. Transform and validate
            # ---------------------------------------------
            for raw_record in extracted_records:
                transformed_record = self.transformer.transform(
                    raw_record
                )

                validation_result = self.validator.validate(
                    transformed_record
                )

                if validation_result.is_valid:
                    valid_records.append(
                        transformed_record
                    )
                else:
                    records_rejected += 1

                    logger.warning(
                        "Order record rejected. "
                        "Order ID: %s. Errors: %s",
                        transformed_record.get("order_id"),
                        validation_result.errors,
                    )

                    with session_scope() as session:
                        session.execute(
                            self.INSERT_ERROR_SQL,
                            {
                                "ingestion_batch_id": batch_id,
                                "source_table": self.SOURCE_TABLE,
                                "source_row_identifier": str(
                                    raw_record["raw_id"]
                                ),
                                "error_type": "validation_error",
                                "error_message": "; ".join(
                                    validation_result.errors
                                ),
                                "raw_payload": self._serialize_payload(
                                    transformed_record
                                ),
                            },
                        )

            logger.info(
                "Order validation completed. "
                "Valid: %s, Rejected: %s",
                len(valid_records),
                records_rejected,
            )

            # ---------------------------------------------
            # 4. Load
            # ---------------------------------------------
            if valid_records:
                with session_scope() as session:
                    loader = OrderLoader(session)

                    loader.load_many(valid_records)

                    records_loaded = len(valid_records)

            logger.info(
                "Order loading completed. Records loaded: %s",
                records_loaded,
            )

            # ---------------------------------------------
            # 5. Complete batch
            # ---------------------------------------------
            with session_scope() as session:
                mark_batch_completed(
                    session,
                    ingestion_batch_id=batch_id,
                    records_received=records_received,
                    records_loaded=records_loaded,
                    records_rejected=records_rejected,
                )

            return OrderPipelineResult(
                ingestion_batch_id=str(batch_id),
                records_received=records_received,
                records_loaded=records_loaded,
                records_rejected=records_rejected,
            )

        except Exception as exc:
            logger.exception(
                "Order ETL pipeline failed. Batch ID: %s",
                batch_id,
            )

            if batch_id is not None:
                try:
                    with session_scope() as session:
                        mark_batch_failed(
                            session,
                            ingestion_batch_id=batch_id,
                            error_message=str(exc),
                            records_received=records_received,
                            records_loaded=records_loaded,
                            records_rejected=records_rejected,
                        )
                except Exception:
                    logger.exception(
                        "Failed to mark order batch as failed."
                    )

            raise

    @staticmethod
    def _serialize_payload(
        record: dict[str, Any],
    ) -> str:
        """Serialize transformed records for JSONB error storage."""
        import json
        from datetime import date, datetime
        from decimal import Decimal

        def default_serializer(value: Any) -> str:
            if isinstance(
                value,
                (date, datetime, Decimal),
            ):
                return str(value)

            return str(value)

        return json.dumps(
            record,
            default=default_serializer,
        )