from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseTransformer(ABC):
    """
    Base interface for transforming a single extracted record
    into a staging-ready record.
    """

    @abstractmethod
    def transform(
        self,
        record: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Transform one source record into a destination-ready record.
        """
        raise NotImplementedError