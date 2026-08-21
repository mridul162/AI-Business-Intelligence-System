"""
Partner capital ETL pipeline.

Pipeline flow:

    raw.partner_capital
        ↓
    PartnerCapitalExtractor
        ↓
    PartnerCapitalTransformer
        ↓
    PartnerCapitalValidator
        ↓
    PartnerCapitalLoader
        ↓
    staging.stg_partner_capital

Each ETL run is tracked through raw.ingestion_batches.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from database.connection import session_scope

from etl.extract.partner_capital_extractor import (
    PartnerCapitalExtractor,
)
from etl.load.partner_capital_loader import PartnerCapitalLoader
from etl.models.validation import ValidationResult
from etl.transform.partner_capital_transformer import (
    PartnerCapitalTransformer,
)
from etl.utils.ingestion_batch import (
    create_ingestion_batch,
    mark_batch_completed,
    mark_batch_failed,
)
from etl.utils.ingestion_error import record_ingestion_error
from etl.validators.partner_capital_validator import (
    PartnerCapitalValidator,
)


logger = logging.getLogger(__name__)


@dataclass
class PartnerCapitalPipelineResult:
    """Summary of a partner capital ETL pipeline run."""

    ingestion_batch_id: str
    records_received: int
    records_loaded: int
    records_rejected: int


class PartnerCapitalPipeline():
    """Orchestrate the complete partner capital ETL pipeline."""

    SOURCE_SYSTEM = "HBMS"
    SOURCE_TYPE = "postgresql"
    SOURCE_REFERENCE = "raw.partner_capital"

    def __init__(self) -> None:
        self.extractor = PartnerCapitalExtractor()
        self.transformer = PartnerCapitalTransformer()
        self.validator = PartnerCapitalValidator()

    def run(self) -> PartnerCapitalPipelineResult:
        """Execute the complete partner capital ETL pipeline."""

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
                "Created partner capital ETL batch: %s",
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
                "partner capital extraction completed. "
                "Records received: %s",
                records_received,
            )

            # ---------------------------------------------
            # 3-5. Transform, validate and load
            # ---------------------------------------------
            with session_scope() as session:
                loader = PartnerCapitalLoader(session)

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
                            "partner capital record rejected. "
                            "entry ID: %s. Errors: %s",
                            transformed_record.get(
                                "partner_capital_entry_id"
                            ),
                            validation_result.errors,
                        )

                        record_ingestion_error(
                            session=session,
                            ingestion_batch_id=batch_id,
                            source_table="partner_capital",
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
                "partner capital validation/loading completed. "
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

            return PartnerCapitalPipelineResult(
                ingestion_batch_id=str(batch_id),
                records_received=records_received,
                records_loaded=records_loaded,
                records_rejected=records_rejected,
            )

        except Exception as exc:
            logger.exception(
                "partner capital ETL pipeline failed. Batch ID: %s",
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
                        "Failed to mark partner capital batch as failed."
                    )

            raise