"""
Customer ETL pipeline.

Pipeline flow:

    raw.customers
        ↓
    CustomerExtractor
        ↓
    CustomerTransformer
        ↓
    CustomerValidator
        ↓
    CustomerLoader
        ↓
    staging.stg_customers

Each pipeline run is tracked through raw.ingestion_batches.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from database.connection import session_scope

from etl.extract.customer_extractor import CustomerExtractor
from etl.load.customer_loader import CustomerLoader
from etl.transform.customer_transformer import CustomerTransformer
from etl.utils.ingestion_batch import (
    create_ingestion_batch,
    mark_batch_completed,
    mark_batch_failed,
)
from etl.validators.customer_validator import CustomerValidator


logger = logging.getLogger(__name__)


@dataclass
class CustomerPipelineResult:
    """Summary of a customer ETL pipeline run."""

    ingestion_batch_id: str
    records_received: int
    records_loaded: int
    records_rejected: int


class CustomerPipeline:
    """
    Orchestrates the customer ETL pipeline.

    The pipeline reads customer records from raw.customers, transforms and
    validates them, loads valid records into staging.stg_customers, and
    tracks the run in raw.ingestion_batches.
    """

    SOURCE_SYSTEM = "HBMS"
    SOURCE_TYPE = "postgresql"
    SOURCE_REFERENCE = "raw.customers"

    def __init__(self) -> None:
        self.extractor = CustomerExtractor()
        self.transformer = CustomerTransformer()
        self.validator = CustomerValidator()

    def run(self) -> CustomerPipelineResult:
        """
        Execute the complete customer ETL pipeline.

        Returns:
            CustomerPipelineResult containing ingestion batch and record counts.

        Raises:
            Exception: Re-raises any unexpected pipeline failure after marking
                the ingestion batch as failed.
        """
        batch_id = None
        records_received = 0
        records_loaded = 0
        records_rejected = 0

        try:
            # -------------------------------------------------
            # 1. Create ingestion batch
            # -------------------------------------------------
            with session_scope() as session:
                batch_id = create_ingestion_batch(
                    session,
                    source_system=self.SOURCE_SYSTEM,
                    source_type=self.SOURCE_TYPE,
                    source_reference=self.SOURCE_REFERENCE,
                )

            logger.info(
                "Created customer ingestion batch: %s",
                batch_id,
            )

            # -------------------------------------------------
            # 2. Extract
            # -------------------------------------------------
            with session_scope() as session:
                extracted_records = self.extractor.extract(session)

            records_received = len(extracted_records)

            logger.info(
                "Customer extraction completed. Records received: %s",
                records_received,
            )

            # -------------------------------------------------
            # 3. Transform
            # -------------------------------------------------
            transformed_records = [
                self.transformer.transform(record)
                for record in extracted_records
            ]

            logger.info(
                "Customer transformation completed."
            )

            # -------------------------------------------------
            # 4. Validate
            # -------------------------------------------------
            valid_records: list[dict[str, Any]] = []

            for record in transformed_records:
                errors = self.validator.validate(record)

                if not errors:
                    valid_records.append(record)
                else:
                    records_rejected += 1

                    logger.warning(
                        "Customer record rejected. "
                        "Customer ID: %s. Errors: %s",
                        record.get("customer_id"),
                        errors,
                    )

            logger.info(
                "Customer validation completed. "
                "Valid: %s, Rejected: %s",
                len(valid_records),
                records_rejected,
            )

            # -------------------------------------------------
            # 5. Load
            # -------------------------------------------------
            if valid_records:
                with session_scope() as session:
                    loader = CustomerLoader(session)

                    for record in valid_records:
                        loader.load(record=record)
                        records_loaded += 1

            logger.info(
                "Customer loading completed. Records loaded: %s",
                records_loaded,
            )
            # -------------------------------------------------
            # 6. Mark batch completed
            # -------------------------------------------------
            with session_scope() as session:
                mark_batch_completed(
                    session,
                    ingestion_batch_id=batch_id,
                    records_received=records_received,
                    records_loaded=records_loaded,
                    records_rejected=records_rejected,
                )

            logger.info(
                "Customer ingestion batch completed successfully: %s",
                batch_id,
            )

            return CustomerPipelineResult(
                ingestion_batch_id=str(batch_id),
                records_received=records_received,
                records_loaded=records_loaded,
                records_rejected=records_rejected,
            )

        except Exception as exc:
            logger.exception(
                "Customer ETL pipeline failed. Batch ID: %s",
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
                        "Failed to update ingestion batch status to failed. "
                        "Batch ID: %s",
                        batch_id,
                    )

            raise