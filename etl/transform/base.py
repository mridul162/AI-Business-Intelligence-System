"""
Base classes for transformation steps.
"""
from abc import ABC, abstractmethod


class BaseTransformer(ABC):
    """Base class that all transformers should inherit from."""

    @abstractmethod
    def transform(self, data, *args, **kwargs):
        """Transform the given data and return the result."""
        raise NotImplementedError
