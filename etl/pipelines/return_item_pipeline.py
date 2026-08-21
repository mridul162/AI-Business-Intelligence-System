"""
Return item ETL pipeline.

Pipeline flow:

    raw.return_items
        ↓
    ReturnItemExtractor
        ↓
    ReturnItemTransformer
        ↓
    ReturnItemValidator
        ↓
    ReturnItemLoader
        ↓
    staging.stg_return_items
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from database.connection import session_scope

from etl.extract.return_item_extractor import (
    ReturnItemExtractor,
)
from etl.load.return_item_loader import (
    ReturnItemLoader,
)
from etl.transform.return_item_transformer import (
    ReturnItemTransformer,
)
from etl.utils.ingestion_batch import (
    create_ingestion_batch,
    mark_batch_completed,
    mark_batch_failed,
)
from etl.utils.ingestion_error import (
    record_ingestion_error,
)
from etl.validators.return_item_validator import (
    ReturnItemValidator,
)


logger = logging.getLogger(__name__)


@dataclass
class ReturnItemPipelineResult:
    """Summary of a return item ETL pipeline run."""

    ingestion_batch_id: str
    records_received: int
    records_loaded: int
    records_rejected: int


class ReturnItemPipeline:
    """
    Orchestrate the return item ETL pipeline.
    """

    SOURCE_SYSTEM = "HBMS"
    SOURCE_TYPE = "postgresql"
    SOURCE_REFERENCE = "raw.return_items"

    def __init__(self) -> None:
        self.extractor = ReturnItemExtractor()
        self.transformer = ReturnItemTransformer()
        self.validator = ReturnItemValidator()

    def run(
        self,
        source_batch_id: str | None = None,
    ) -> ReturnItemPipelineResult:
        """
        Execute the complete return item ETL pipeline.

        source_batch_id can optionally restrict extraction to one
        raw ingestion batch.
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
                "Created return item ETL batch: %s",
                pipeline_batch_id,
            )

            # ---------------------------------------------
            # 2. Extract
            # ---------------------------------------------
            with session_scope() as session:
                extracted_records = self.extractor.extract(
                    session,
                    batch_id=source_batch_id,
                )

            records_received = len(
                extracted_records
            )

            logger.info(
                "Return item extraction completed. "
                "Records received: %s",
                records_received,
            )

            # ---------------------------------------------
            # 3. Transform and validate
            # ---------------------------------------------
            records_to_load: list[dict[str, Any]] = []

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
                    transformed_record[
                        "record_status"
                    ] = "pending"

                    transformed_record[
                        "validation_error"
                    ] = None

                    records_to_load.append(
                        transformed_record
                    )

                else:
                    records_rejected += 1

                    transformed_record[
                        "record_status"
                    ] = "invalid"

                    transformed_record[
                        "validation_error"
                    ] = "; ".join(
                        validation_result.errors
                    )

                    with session_scope() as session:
                        record_ingestion_error(
                            session,
                            ingestion_batch_id=(
                                pipeline_batch_id
                            ),
                            source_table="return_items",
                            source_row_identifier=str(
                                raw_record["raw_id"]
                            ),
                            error_type="validation_error",
                            error_message="; ".join(
                                validation_result.errors
                            ),
                            raw_payload=transformed_record,
                        )

                    logger.warning(
                        "Return item record rejected. "
                        "Return Item ID: %s. Errors: %s",
                        transformed_record.get(
                            "return_item_id"
                        ),
                        validation_result.errors,
                    )

            # ---------------------------------------------
            # 4. Load valid records
            # ---------------------------------------------
            if records_to_load:
                with session_scope() as session:
                    loader = ReturnItemLoader(
                        session
                    )

                    records_loaded = loader.load_many(
                        records_to_load
                    )

            logger.info(
                "Return item loading completed. "
                "Records loaded: %s",
                records_loaded,
            )

            # ---------------------------------------------
            # 5. Mark batch completed
            # ---------------------------------------------
            with session_scope() as session:
                mark_batch_completed(
                    session,
                    ingestion_batch_id=pipeline_batch_id,
                    records_received=records_received,
                    records_loaded=records_loaded,
                    records_rejected=records_rejected,
                )

            return ReturnItemPipelineResult(
                ingestion_batch_id=str(
                    pipeline_batch_id
                ),
                records_received=records_received,
                records_loaded=records_loaded,
                records_rejected=records_rejected,
            )

        except Exception as exc:
            logger.exception(
                "Return item ETL pipeline failed. "
                "Batch ID: %s",
                pipeline_batch_id,
            )

            if pipeline_batch_id is not None:
                try:
                    with session_scope() as session:
                        mark_batch_failed(
                            session,
                            ingestion_batch_id=(
                                pipeline_batch_id
                            ),
                            error_message=str(exc),
                            records_received=records_received,
                            records_loaded=records_loaded,
                            records_rejected=records_rejected,
                        )
                except Exception:
                    logger.exception(
                        "Failed to mark return item batch "
                        "as failed. Batch ID: %s",
                        pipeline_batch_id,
                    )

            raise