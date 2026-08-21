from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session


class BaseLoader(ABC):
    """
    Base interface for loading validated records into a destination table.
    """

    @abstractmethod
    def load(
        self,
        record: dict[str, Any],
        *,
        validation_errors: list[str] | None = None,
    ) -> None:
        """
        Load a single record into the destination.
        """
        raise NotImplementedError

    @abstractmethod
    def load_many(
        self,
        records: list[dict[str, Any]],
    ) -> None:
        """
        Load multiple records into the destination.
        """
        raise NotImplementedError