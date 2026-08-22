"""
Main warehouse validation orchestrator.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from etl.warehouse.validation.dimension_validator import (
    DimensionValidationResult,
    DimensionValidator,
)
from etl.warehouse.validation.fact_validator import (
    FactValidationResult,
    FactValidator,
)
from etl.warehouse.validation.reconciliation_validator import (
    ReconciliationResult,
    ReconciliationValidator,
)


@dataclass
class WarehouseValidationReport:
    """Complete warehouse validation report."""

    dimensions: list[DimensionValidationResult]
    facts: list[FactValidationResult]
    reconciliations: list[ReconciliationResult]

    @property
    def dimensions_valid(self) -> bool:
        """Return whether all dimensions passed."""

        return all(
            result.is_valid
            for result in self.dimensions
        )

    @property
    def facts_valid(self) -> bool:
        """Return whether all facts passed."""

        return all(
            result.is_valid
            for result in self.facts
        )

    @property
    def reconciliations_valid(self) -> bool:
        """Return whether all reconciliations passed."""

        return all(
            result.is_valid
            for result in self.reconciliations
        )

    @property
    def is_valid(self) -> bool:
        """Return whether the entire warehouse passed."""

        return (
            self.dimensions_valid
            and self.facts_valid
            and self.reconciliations_valid
        )


class WarehouseValidator:
    """Run all warehouse validation checks."""

    def __init__(
        self,
        session: Session,
    ) -> None:
        self.dimension_validator = (
            DimensionValidator(session)
        )

        self.fact_validator = (
            FactValidator(session)
        )

        self.reconciliation_validator = (
            ReconciliationValidator(session)
        )

    def validate(
        self,
    ) -> WarehouseValidationReport:
        """Run the complete warehouse validation."""

        dimensions = (
            self.dimension_validator.validate_all()
        )

        facts = (
            self.fact_validator.validate_all()
        )

        reconciliations = (
            self.reconciliation_validator.validate_all()
        )

        return WarehouseValidationReport(
            dimensions=dimensions,
            facts=facts,
            reconciliations=reconciliations,
        )