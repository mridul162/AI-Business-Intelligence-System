from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from etl.models.validation import ValidationResult


class BaseValidator(ABC):
    """
    Base interface for validating transformed ETL records.
    """

    @abstractmethod
    def validate(
        self,
        record: dict[str, Any],
    ) -> ValidationResult:
        """
        Validate one transformed record.

        Returns:
            ValidationResult containing validation status and errors.
        """
        raise NotImplementedError