"""
Payment ETL pipeline.

Pipeline flow:

    raw.payments
        ↓
    PaymentExtractor
        ↓
    PaymentTransformer
        ↓
    PaymentValidator
        ↓
    PaymentLoader
        ↓
    staging.stg_payments

Invalid records are recorded in raw.ingestion_errors.
Each pipeline run is tracked through raw.ingestion_batches.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from database.connection import session_scope

from etl.extract.payment_extractor import PaymentExtractor
from etl.load.payment_loader import PaymentLoader
from etl.transform.payment_transformer import PaymentTransformer
from etl.utils.ingestion_batch import (
    create_ingestion_batch,
    mark_batch_completed,
    mark_batch_failed,
)
from etl.utils.ingestion_error import record_ingestion_error
from etl.validators.payment_validator import PaymentValidator


logger = logging.getLogger(__name__)


@dataclass
class PaymentPipelineResult:
    """Summary of a payment ETL pipeline run."""

    ingestion_batch_id: str
    records_received: int
    records_loaded: int
    records_rejected: int


class PaymentPipeline:
    """
    Orchestrate extraction, transformation, validation, and loading
    of payment records.
    """

    SOURCE_SYSTEM = "HBMS"
    SOURCE_TYPE = "postgresql"
    SOURCE_REFERENCE = "raw.payments"

    def __init__(self) -> None:
        self.extractor = PaymentExtractor()
        self.transformer = PaymentTransformer()
        self.validator = PaymentValidator()

    def run(
        self,
        source_batch_id: str | None = None,
    ) -> PaymentPipelineResult:
        """
        Execute the complete payment ETL pipeline.

        source_batch_id can be used to process records from one
        specific raw ingestion batch.
        """

        pipeline_batch_id = None
        records_received = 0
        records_loaded = 0
        records_rejected = 0

        try:
            # ---------------------------------------------
            # 1. Create ETL ingestion batch
            # ---------------------------------------------
            with session_scope() as session:
                pipeline_batch_id = create_ingestion_batch(
                    session,
                    source_system=self.SOURCE_SYSTEM,
                    source_type=self.SOURCE_TYPE,
                    source_reference=self.SOURCE_REFERENCE,
                )

            logger.info(
                "Created payment ETL batch: %s",
                pipeline_batch_id,
            )

            # ---------------------------------------------
            # 2. Extract
            # ---------------------------------------------
            with session_scope() as session:
                extracted_records = self.extractor.extract(
                    session=session,
                    batch_id=source_batch_id,
                )

            records_received = len(extracted_records)

            logger.info(
                "Payment extraction completed. "
                "Records received: %s",
                records_received,
            )

            # ---------------------------------------------
            # 3–5. Transform, Validate, Load
            # ---------------------------------------------
            with session_scope() as session:
                loader = PaymentLoader(session)

                for raw_record in extracted_records:
                    transformed_record = (
                        self.transformer.transform(
                            raw_record
                        )
                    )

                    validation_result = (
                        self.validator.validate(
                            transformed_record
                        )
                    )

                    if validation_result.is_valid:
                        loader.load(
                            transformed_record,
                        )

                        records_loaded += 1

                    else:
                        records_rejected += 1

                        logger.warning(
                            "Payment record rejected. "
                            "Payment ID: %s. Errors: %s",
                            transformed_record.get(
                                "payment_id"
                            ),
                            validation_result.errors,
                        )

                        record_ingestion_error(
                            session=session,
                            ingestion_batch_id=pipeline_batch_id,
                            source_table="payments",
                            source_row_identifier=
                                transformed_record.get(
                                    "source_row_identifier"
                                ),
                            error_type="validation_error",
                            error_message="; ".join(
                                validation_result.errors
                            ),
                            raw_payload=transformed_record,
                        )

            # ---------------------------------------------
            # 6. Complete batch
            # ---------------------------------------------
            with session_scope() as session:
                mark_batch_completed(
                    session,
                    ingestion_batch_id=pipeline_batch_id,
                    records_received=records_received,
                    records_loaded=records_loaded,
                    records_rejected=records_rejected,
                )

            logger.info(
                "Payment ETL batch completed successfully: %s",
                pipeline_batch_id,
            )

            return PaymentPipelineResult(
                ingestion_batch_id=str(
                    pipeline_batch_id
                ),
                records_received=records_received,
                records_loaded=records_loaded,
                records_rejected=records_rejected,
            )

        except Exception as exc:
            logger.exception(
                "Payment ETL pipeline failed. Batch ID: %s",
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
                        "Failed to mark payment batch as failed."
                    )

            raise