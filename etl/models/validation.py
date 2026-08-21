from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ValidationResult:
    """
    Result of validating a transformed ETL record.
    """

    errors: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """Return True when the record has no validation errors."""
        return not self.errors