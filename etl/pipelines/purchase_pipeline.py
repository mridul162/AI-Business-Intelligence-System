"""
Purchase ETL pipeline.

Pipeline flow:

    raw.purchases
        ↓
    PurchaseExtractor
        ↓
    PurchaseTransformer
        ↓
    PurchaseValidator
        ↓
    PurchaseLoader
        ↓
    staging.stg_purchases

Each ETL run is tracked through raw.ingestion_batches.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from database.connection import session_scope

from etl.extract.purchase_extractor import PurchaseExtractor
from etl.load.purchase_loader import PurchaseLoader
from etl.models.validation import ValidationResult
from etl.transform.purchase_transformer import PurchaseTransformer
from etl.utils.ingestion_batch import (
    create_ingestion_batch,
    mark_batch_completed,
    mark_batch_failed,
)
from etl.utils.ingestion_error import record_ingestion_error
from etl.validators.purchase_validator import PurchaseValidator


logger = logging.getLogger(__name__)


@dataclass
class PurchasePipelineResult:
    """Summary of a purchase ETL pipeline run."""

    ingestion_batch_id: str
    records_received: int
    records_loaded: int
    records_rejected: int


class PurchasePipeline():
    """Orchestrate the complete purchases ETL pipeline."""

    SOURCE_SYSTEM = "HBMS"
    SOURCE_TYPE = "postgresql"
    SOURCE_REFERENCE = "raw.purchases"

    def __init__(self) -> None:
        self.extractor = PurchaseExtractor()
        self.transformer = PurchaseTransformer()
        self.validator = PurchaseValidator()

    def run(self) -> PurchasePipelineResult:
        """Execute the complete purchase ETL pipeline."""

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
                "Created purchase ETL batch: %s",
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
                "purchase extraction completed. "
                "Records received: %s",
                records_received,
            )

            # ---------------------------------------------
            # 3-5. Transform, validate and load
            # ---------------------------------------------
            with session_scope() as session:
                loader = PurchaseLoader(session)

                for raw_record in extracted_records:
                    transformed_record = (
                        self.transformer.transform(
                            raw_record
                        )
                    )

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
                            "purchase record rejected. "
                            "purchase ID: %s. Errors: %s",
                            transformed_record.get(
                                "purchase_id"
                            ),
                            validation_result.errors,
                        )

                        record_ingestion_error(
                            session=session,
                            ingestion_batch_id=batch_id,
                            source_table="purchases",
                            source_row_identifier=str(
                                raw_record["raw_id"]
                            ),
                            error_type="validation_error",
                            error_message="; ".join(
                                validation_result.errors
                            ),
                            raw_payload={
                                key: value
                                for key, value in (
                                    transformed_record.items()
                                )
                                if key != "_parse_errors"
                            },
                        )

            logger.info(
                "purchase validation/loading completed. "
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

            return PurchasePipelineResult(
                ingestion_batch_id=str(batch_id),
                records_received=records_received,
                records_loaded=records_loaded,
                records_rejected=records_rejected,
            )

        except Exception as exc:
            logger.exception(
                "purchase ETL pipeline failed. Batch ID: %s",
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
                        "Failed to mark purchase batch as failed."
                    )

            raise