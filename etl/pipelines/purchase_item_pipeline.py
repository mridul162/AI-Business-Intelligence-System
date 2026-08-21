"""
Purchase item ETL pipeline.

Pipeline flow:

    raw.purchase_items
        ↓
    PurchaseItemExtractor
        ↓
    PurchaseItemTransformer
        ↓
    PurchaseItemValidator
        ↓
    PurchaseItemLoader
        ↓
    staging.stg_purchase_items

Each ETL run is tracked through raw.ingestion_batches.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from database.connection import session_scope

from etl.extract.purchase_item_extractor import PurchaseItemExtractor
from etl.load.purchase_item_loader import PurchaseItemLoader
from etl.models.validation import ValidationResult
from etl.transform.purchase_item_transformer import PurchaseItemTransformer
from etl.utils.ingestion_batch import (
    create_ingestion_batch,
    mark_batch_completed,
    mark_batch_failed,
)
from etl.utils.ingestion_error import record_ingestion_error
from etl.validators.purchase_item_validator import PurchaseItemValidator


logger = logging.getLogger(__name__)


@dataclass
class PurchaseItemPipelineResult:
    """Summary of a purchase item ETL pipeline run."""

    ingestion_batch_id: str
    records_received: int
    records_loaded: int
    records_rejected: int


class PurchaseItemPipeline():
    """Orchestrate the complete purchase items ETL pipeline."""

    SOURCE_SYSTEM = "HBMS"
    SOURCE_TYPE = "postgresql"
    SOURCE_REFERENCE = "raw.purchase_items"

    def __init__(self) -> None:
        self.extractor = PurchaseItemExtractor()
        self.transformer = PurchaseItemTransformer()
        self.validator = PurchaseItemValidator()

    def run(self) -> PurchaseItemPipelineResult:
        """Execute the complete purchase item ETL pipeline."""

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
                "Created purchase item ETL batch: %s",
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
                "purchase item extraction completed. "
                "Records received: %s",
                records_received,
            )

            # ---------------------------------------------
            # 3-5. Transform, validate and load
            # ---------------------------------------------
            with session_scope() as session:
                loader = PurchaseItemLoader(session)

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
                            "purchase item record rejected "
                            "during transform. raw_id: %s. "
                            "Error: %s",
                            raw_record.get("raw_id"),
                            exc,
                        )

                        record_ingestion_error(
                            session=session,
                            ingestion_batch_id=batch_id,
                            source_table="purchase_items",
                            source_row_identifier=str(
                                raw_record["raw_id"]
                            ),
                            error_type="transformation_error",
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
                            "purchase item record rejected. "
                            "purchase item ID: %s. Errors: %s",
                            transformed_record.get(
                                "purchase_item_id"
                            ),
                            validation_result.errors,
                        )

                        record_ingestion_error(
                            session=session,
                            ingestion_batch_id=batch_id,
                            source_table="purchase_items",
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
                "purchase item validation/loading completed. "
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

            return PurchaseItemPipelineResult(
                ingestion_batch_id=str(batch_id),
                records_received=records_received,
                records_loaded=records_loaded,
                records_rejected=records_rejected,
            )

        except Exception as exc:
            logger.exception(
                "purchase item ETL pipeline failed. Batch ID: %s",
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
                        "Failed to mark purchase item batch as failed."
                    )

            raise