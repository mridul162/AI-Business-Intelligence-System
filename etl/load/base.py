"""
Base classes for load steps.
"""
from abc import ABC, abstractmethod


class BaseLoader(ABC):
    """Base class that all loaders should inherit from."""

    @abstractmethod
    def load(self, data, *args, **kwargs):
        """Load the given data into a destination."""
        raise NotImplementedError
