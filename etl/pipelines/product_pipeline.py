"""
Product ETL pipeline.

Pipeline flow:

    raw.products
        ↓
    ProductExtractor
        ↓
    ProductTransformer
        ↓
    ProductValidator
        ↓
    ProductLoader
        ↓
    staging.stg_products

Each pipeline run is tracked through raw.ingestion_batches.
Invalid records are recorded in raw.ingestion_errors.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from database.connection import session_scope

from etl.extract.product_extractor import ProductExtractor
from etl.load.product_loader import ProductLoader
from etl.transform.product_transformer import ProductTransformer
from etl.utils.ingestion_batch import (
    create_ingestion_batch,
    mark_batch_completed,
    mark_batch_failed,
)
from etl.utils.ingestion_error import record_ingestion_error
from etl.validators.product_validator import ProductValidator


logger = logging.getLogger(__name__)


@dataclass
class ProductPipelineResult:
    """Summary of a product ETL pipeline run."""

    ingestion_batch_id: str
    records_received: int
    records_loaded: int
    records_rejected: int


class ProductPipeline:
    """
    Orchestrates the product ETL pipeline.

    Reads product records from raw.products, transforms and validates them,
    loads valid records into staging.stg_products, records invalid rows in
    raw.ingestion_errors, and tracks the ETL run in raw.ingestion_batches.
    """

    SOURCE_SYSTEM = "HBMS"
    SOURCE_TYPE = "postgresql"
    SOURCE_REFERENCE = "raw.products"

    def __init__(self) -> None:
        self.extractor = ProductExtractor()
        self.transformer = ProductTransformer()
        self.validator = ProductValidator()

    def run(
        self,
        source_batch_id: str | None = None,
    ) -> ProductPipelineResult:
        """
        Execute the complete product ETL pipeline.

        Args:
            source_batch_id: Optional raw ingestion batch ID. When provided,
                only products from that raw ingestion batch are processed.

        Returns:
            ProductPipelineResult containing the ETL batch and record counts.

        Raises:
            Exception: Re-raises unexpected failures after marking the
                ETL ingestion batch as failed.
        """
        batch_id: str | None = None
        records_received = 0
        records_loaded = 0
        records_rejected = 0

        try:
            # -------------------------------------------------
            # 1. Create ETL ingestion batch
            # -------------------------------------------------
            with session_scope() as session:
                batch_id = str(
                    create_ingestion_batch(
                        session,
                        source_system=self.SOURCE_SYSTEM,
                        source_type=self.SOURCE_TYPE,
                        source_reference=self.SOURCE_REFERENCE,
                    )
                )

            logger.info(
                "Created product ETL batch: %s",
                batch_id,
            )

            # -------------------------------------------------
            # 2. Extract
            # -------------------------------------------------
            with session_scope() as session:
                extracted_records = self.extractor.extract(
                    session=session,
                    batch_id=source_batch_id,
                )

            records_received = len(extracted_records)

            logger.info(
                "Product extraction completed. Records received: %s",
                records_received,
            )

            # -------------------------------------------------
            # 3. Transform + Validate
            # -------------------------------------------------
            valid_records: list[dict[str, Any]] = []

            for raw_record in extracted_records:
                transformed_record = self.transformer.transform(
                    raw_record
                )

                validation_result = self.validator.validate(
                    transformed_record
                )

                if validation_result.is_valid:
                    valid_records.append(transformed_record)
                else:
                    records_rejected += 1

                    logger.warning(
                        "Product record rejected. Product ID: %s. "
                        "Errors: %s",
                        transformed_record.get("product_id"),
                        validation_result.errors,
                    )

                    with session_scope() as session:
                        record_ingestion_error(
                            session,
                            ingestion_batch_id=batch_id,
                            source_table="products",
                            source_row_identifier=transformed_record[
                                "source_row_identifier"
                            ],
                            error_type="validation_error",
                            error_message="; ".join(
                                validation_result.errors
                            ),
                            raw_payload=transformed_record,
                        )

            logger.info(
                "Product validation completed. Valid: %s, Rejected: %s",
                len(valid_records),
                records_rejected,
            )

            # -------------------------------------------------
            # 4. Load valid records
            # -------------------------------------------------
            if valid_records:
                with session_scope() as session:
                    loader = ProductLoader(session)

                    loader.load_many(valid_records)

                records_loaded = len(valid_records)

            logger.info(
                "Product loading completed. Records loaded: %s",
                records_loaded,
            )

            # -------------------------------------------------
            # 5. Mark ETL batch completed
            # -------------------------------------------------
            with session_scope() as session:
                mark_batch_completed(
                    session,
                    ingestion_batch_id=batch_id, # type: ignore
                    records_received=records_received,
                    records_loaded=records_loaded,
                    records_rejected=records_rejected,
                )

            logger.info(
                "Product ETL batch completed successfully: %s",
                batch_id,
            )

            return ProductPipelineResult(
                ingestion_batch_id=batch_id,
                records_received=records_received,
                records_loaded=records_loaded,
                records_rejected=records_rejected,
            )

        except Exception as exc:
            logger.exception(
                "Product ETL pipeline failed. Batch ID: %s",
                batch_id,
            )

            if batch_id is not None:
                try:
                    with session_scope() as session:
                        mark_batch_failed(
                            session,
                            ingestion_batch_id=batch_id, # type: ignore
                            error_message=str(exc),
                            records_received=records_received,
                            records_loaded=records_loaded,
                            records_rejected=records_rejected,
                        )
                except Exception:
                    logger.exception(
                        "Failed to mark product ETL batch as failed. "
                        "Batch ID: %s",
                        batch_id,
                    )

            raise