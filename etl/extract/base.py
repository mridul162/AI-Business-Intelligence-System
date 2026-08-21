from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session


class BaseExtractor(ABC):
    """
    Base interface for extracting records from a source table.
    """

    @abstractmethod
    def extract(
        self,
        session: Session,
        batch_id: UUID | None = None,
    ) -> list[dict[str, Any]]:
        """
        Extract records from a source table.

        Args:
            session: Active SQLAlchemy database session.
            batch_id: Optional ingestion batch ID used to filter records.

        Returns:
            A list of extracted source records.
        """
        raise NotImplementedError