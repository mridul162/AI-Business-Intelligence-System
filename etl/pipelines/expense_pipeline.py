"""
Expense ETL pipeline.

Pipeline flow:

    raw.expenses
        ↓
    ExpenseExtractor
        ↓
    ExpenseTransformer
        ↓
    ExpenseValidator
        ↓
    ExpenseLoader
        ↓
    staging.stg_expenses

Each ETL run is tracked through raw.ingestion_batches.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from database.connection import session_scope

from etl.extract.expense_extractor import ExpenseExtractor
from etl.load.expense_loader import ExpenseLoader
from etl.models.validation import ValidationResult
from etl.transform.expense_transformer import ExpenseTransformer
from etl.utils.ingestion_batch import (
    create_ingestion_batch,
    mark_batch_completed,
    mark_batch_failed,
)
from etl.utils.ingestion_error import record_ingestion_error
from etl.validators.expense_validator import ExpenseValidator


logger = logging.getLogger(__name__)


@dataclass
class ExpensePipelineResult:
    """Summary of an expense ETL pipeline run."""

    ingestion_batch_id: str
    records_received: int
    records_loaded: int
    records_rejected: int


class ExpensePipeline():
    """Orchestrate the complete expenses ETL pipeline."""

    SOURCE_SYSTEM = "HBMS"
    SOURCE_TYPE = "postgresql"
    SOURCE_REFERENCE = "raw.expenses"

    def __init__(self) -> None:
        self.extractor = ExpenseExtractor()
        self.transformer = ExpenseTransformer()
        self.validator = ExpenseValidator()

    def run(self) -> ExpensePipelineResult:
        """Execute the complete expense ETL pipeline."""

        batch_id = None
        records_received = 0
        records_loaded = 0
        records_rejected = 0

        try:
            # ---------------------------------------------
            # 1. Create ETL processing batch
            # ---------------------------------------------
            with session_scope() as session:
                if batch_id is None:
                    batch_id = create_ingestion_batch(
                        session,
                        source_system=self.SOURCE_SYSTEM,
                        source_type=self.SOURCE_TYPE,
                        source_reference=self.SOURCE_REFERENCE,
                    )

            logger.info(
                "Created expense ETL batch: %s",
                batch_id,
            )

            # ---------------------------------------------
            # 2. Extract raw records
            # ---------------------------------------------
            with session_scope() as session:
                extracted_records = self.extractor.extract(
                    session=session,
                )

            records_received = len(extracted_records)

            logger.info(
                "expense extraction completed. "
                "Records received: %s",
                records_received,
            )

            # ---------------------------------------------
            # 3-5. Transform, validate and load
            # ---------------------------------------------
            with session_scope() as session:
                loader = ExpenseLoader(session)

                for raw_record in extracted_records:
                    try:
                        transformed_record = (
                            self.transformer.transform(
                                raw_record
                            )
                        )
                    except ValueError as exc:
                        records_rejected += 1

                        logger.warning(
                            "expense record rejected during "
                            "transform. raw_id: %s. Error: %s",
                            raw_record.get("raw_id"),
                            exc,
                        )

                        record_ingestion_error(
                            session=session,
                            ingestion_batch_id=batch_id,
                            source_table="expenses",
                            source_row_identifier=str(
                                raw_record["raw_id"]
                            ),
                            error_type="transform_error",
                            error_message=str(exc),
                            raw_payload=raw_record,
                        )

                        continue

                    validation_result: ValidationResult = (
                        self.validator.validate(
                            transformed_record
                        )
                    )

                    if validation_result.is_valid:
                        loader.load(
                            transformed_record
                        )
                        records_loaded += 1

                    else:
                        records_rejected += 1

                        logger.warning(
                            "expense record rejected. "
                            "expense ID: %s. Errors: %s",
                            transformed_record.get(
                                "expense_id"
                            ),
                            validation_result.errors,
                        )

                        record_ingestion_error(
                            session=session,
                            ingestion_batch_id=batch_id,
                            source_table="expenses",
                            source_row_identifier=str(
                                raw_record["raw_id"]
                            ),
                            error_type="validation_error",
                            error_message="; ".join(
                                validation_result.errors
                            ),
                            raw_payload=transformed_record,
                        )

            logger.info(
                "expense validation/loading completed. "
                "Loaded: %s, Rejected: %s",
                records_loaded,
                records_rejected,
            )

            # ---------------------------------------------
            # 6. Complete batch
            # ---------------------------------------------
            with session_scope() as session:
                mark_batch_completed(
                    session,
                    ingestion_batch_id=batch_id,
                    records_received=records_received,
                    records_loaded=records_loaded,
                    records_rejected=records_rejected,
                )

            return ExpensePipelineResult(
                ingestion_batch_id=str(batch_id),
                records_received=records_received,
                records_loaded=records_loaded,
                records_rejected=records_rejected,
            )

        except Exception as exc:
            logger.exception(
                "expense ETL pipeline failed. Batch ID: %s",
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
                        "Failed to mark expense batch as failed."
                    )

            raise