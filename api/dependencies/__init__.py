"""Analytics API dependencies."""

from .analytics import (
    build_analytics_application,
    get_analytics_application,
    get_nl_completion,
)

__all__ = [
    "build_analytics_application",
    "get_analytics_application",
    "get_nl_completion",
]
