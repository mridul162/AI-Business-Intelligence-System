"""Analytics API dependencies."""

from __future__ import annotations

from etl.analytics.application.analytics_application import AnalyticsApplication
from etl.analytics.application.factory import get_analytics_application

__all__ = ["get_analytics_application", "AnalyticsApplication"]