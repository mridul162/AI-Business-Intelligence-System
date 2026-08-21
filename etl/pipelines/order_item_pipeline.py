"""
Order item ETL pipeline.

Pipeline flow:

    raw.order_items
        ↓
    OrderItemExtractor
        ↓
    OrderItemTransformer
        ↓
    OrderItemValidator
        ↓
    OrderItemLoader
        ↓
    staging.stg_order_items
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from database.connection import session_scope

from etl.extract.order_item_extractor import OrderItemExtractor
from etl.load.order_item_loader import OrderItemLoader
from etl.models.validation import ValidationResult
from etl.utils.ingestion_error import record_ingestion_error
from etl.transform.order_item_transformer import OrderItemTransformer
from etl.utils.ingestion_batch import (
    create_ingestion_batch,
    mark_batch_completed,
    mark_batch_failed,
)
from etl.validators.order_item_validator import OrderItemValidator


logger = logging.getLogger(__name__)


@dataclass
class OrderItemPipelineResult:
    """Summary of an order item ETL pipeline run."""

    ingestion_batch_id: str
    records_received: int
    records_loaded: int
    records_rejected: int


class OrderItemPipeline:
    """Orchestrate the order item ETL process."""

    SOURCE_SYSTEM = "HBMS"
    SOURCE_TYPE = "postgresql"
    SOURCE_REFERENCE = "raw.order_items"
    SOURCE_TABLE = "order_items"

    def __init__(self) -> None:
        self.extractor = OrderItemExtractor()
        self.transformer = OrderItemTransformer()
        self.validator = OrderItemValidator()

    def run(
        self,
        source_batch_id: str | None = None,
    ) -> OrderItemPipelineResult:
        """
        Execute the complete order item ETL pipeline.

        If source_batch_id is provided, only raw records belonging to that
        raw ingestion batch are processed.
        """

        pipeline_batch_id = None
        records_received = 0
        records_loaded = 0
        records_rejected = 0

        try:
            # 1. Create ETL batch
            with session_scope() as session:
                pipeline_batch_id = create_ingestion_batch(
                    session,
                    source_system=self.SOURCE_SYSTEM,
                    source_type=self.SOURCE_TYPE,
                    source_reference=self.SOURCE_REFERENCE,
                )

            # 2. Extract
            with session_scope() as session:
                extracted_records = self.extractor.extract(
                    session,
                    batch_id=source_batch_id,
                )

            records_received = len(extracted_records)

            logger.info(
                "Order item extraction completed. Records received: %s",
                records_received,
            )

            # 3. Transform + Validate
            valid_records: list[dict[str, Any]] = []

            for raw_record in extracted_records:
                try:
                    transformed_record = self.transformer.transform(
                        raw_record
                    )

                    validation_result: ValidationResult = (
                        self.validator.validate(transformed_record)
                    )

                    if validation_result.is_valid:
                        valid_records.append(transformed_record)
                    else:
                        records_rejected += 1

                        logger.warning(
                            "Order item rejected. Order Item ID: %s. "
                            "Errors: %s",
                            transformed_record.get("order_item_id"),
                            validation_result.errors,
                        )

                        with session_scope() as session:
                            record_ingestion_error(
                                session=session,
                                ingestion_batch_id=pipeline_batch_id,
                                source_table=self.SOURCE_TABLE,
                                source_row_identifier=str(
                                    raw_record["raw_id"]
                                ),
                                error_type="validation_error",
                                error_message="; ".join(
                                    validation_result.errors
                                ),
                                raw_payload=transformed_record,
                            )

                except Exception as exc:
                    records_rejected += 1

                    logger.exception(
                        "Order item transformation failed. Raw ID: %s",
                        raw_record.get("raw_id"),
                    )

                    with session_scope() as session:
                        record_ingestion_error(
                            session=session,
                            ingestion_batch_id=pipeline_batch_id,
                            source_table=self.SOURCE_TABLE,
                            source_row_identifier=str(
                                raw_record["raw_id"]
                            ),
                            error_type="transformation_error",
                            error_message=str(exc),
                            raw_payload=raw_record,
                        )

            # 4. Load valid records
            if valid_records:
                with session_scope() as session:
                    loader = OrderItemLoader(session)

                    records_loaded = loader.load_many(
                        valid_records
                    )

            # 5. Complete batch
            with session_scope() as session:
                mark_batch_completed(
                    session,
                    ingestion_batch_id=pipeline_batch_id,
                    records_received=records_received,
                    records_loaded=records_loaded,
                    records_rejected=records_rejected,
                )

            logger.info(
                "Order item ETL completed successfully. "
                "Batch ID: %s",
                pipeline_batch_id,
            )

            return OrderItemPipelineResult(
                ingestion_batch_id=str(pipeline_batch_id),
                records_received=records_received,
                records_loaded=records_loaded,
                records_rejected=records_rejected,
            )

        except Exception as exc:
            logger.exception(
                "Order item ETL pipeline failed. Batch ID: %s",
                pipeline_batch_id,
            )

            if pipeline_batch_id is not None:
                try:
                    with session_scope() as session:
                        mark_batch_failed(
                            session,
                            ingestion_batch_id=pipeline_batch_id,
                            error_message=str(exc),
                            records_received=records_received,
                            records_loaded=records_loaded,
                            records_rejected=records_rejected,
                        )
                except Exception:
                    logger.exception(
                        "Failed to mark order item batch as failed."
                    )

            raise