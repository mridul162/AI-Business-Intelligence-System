from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from sqlalchemy.orm import Session


class BaseExtractor(ABC):
    """Base interface for extracting data from source tables."""

    @abstractmethod
    def extract(
        self,
        session: Session,
        batch_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Extract records from a source table."""
        raise NotImplementedError