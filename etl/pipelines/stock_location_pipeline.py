"""
Stock location ETL pipeline.

Pipeline flow:

    raw.stock_locations
        ↓
    StockLocationExtractor
        ↓
    StockLocationTransformer
        ↓
    StockLocationValidator
        ↓
    StockLocationLoader
        ↓
    staging.stg_stock_locations

Each ETL run is tracked through raw.ingestion_batches.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from database.connection import session_scope

from etl.extract.stock_location_extractor import (
    StockLocationExtractor,
)
from etl.load.stock_location_loader import StockLocationLoader
from etl.models.validation import ValidationResult
from etl.transform.stock_location_transformer import (
    StockLocationTransformer,
)
from etl.utils.ingestion_batch import (
    create_ingestion_batch,
    mark_batch_completed,
    mark_batch_failed,
)
from etl.utils.ingestion_error import record_ingestion_error
from etl.validators.stock_location_validator import (
    StockLocationValidator,
)


logger = logging.getLogger(__name__)


@dataclass
class StockLocationPipelineResult:
    """Summary of a stock location ETL pipeline run."""

    ingestion_batch_id: str
    records_received: int
    records_loaded: int
    records_rejected: int


class StockLocationPipeline():
    """Orchestrate the complete stock locations ETL pipeline."""

    SOURCE_SYSTEM = "HBMS"
    SOURCE_TYPE = "postgresql"
    SOURCE_REFERENCE = "raw.stock_locations"

    def __init__(self) -> None:
        self.extractor = StockLocationExtractor()
        self.transformer = StockLocationTransformer()
        self.validator = StockLocationValidator()

    def run(self) -> StockLocationPipelineResult:
        """Execute the complete stock location ETL pipeline."""

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
                "Created stock location ETL batch: %s",
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
                "stock location extraction completed. "
                "Records received: %s",
                records_received,
            )

            # ---------------------------------------------
            # 3-5. Transform, validate and load
            # ---------------------------------------------
            with session_scope() as session:
                loader = StockLocationLoader(session)

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
                            "stock location record rejected. "
                            "stock location ID: %s. Errors: %s",
                            transformed_record.get(
                                "stock_location_id"
                            ),
                            validation_result.errors,
                        )

                        record_ingestion_error(
                            session=session,
                            ingestion_batch_id=batch_id,
                            source_table="stock_locations",
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
                "stock location validation/loading completed. "
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

            return StockLocationPipelineResult(
                ingestion_batch_id=str(batch_id),
                records_received=records_received,
                records_loaded=records_loaded,
                records_rejected=records_rejected,
            )

        except Exception as exc:
            logger.exception(
                "stock location ETL pipeline failed. Batch ID: %s",
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
                        "Failed to mark stock location batch as failed."
                    )

            raise