from __future__ import annotations

from etl.data_quality.models import DataQualityReport
from etl.data_quality.registry import DataQualityRegistry


class DataQualityRunner:
    """Simple runner for executing registered data-quality checks."""

    def __init__(self, session: object, registry: DataQualityRegistry | None = None) -> None:
        self.session = session
        self.registry = registry or DataQualityRegistry()

    def run(self) -> DataQualityReport:
        return self.registry.run(self.session)

    def add_check(self, check) -> None:
        self.registry.register(check)

    def add_checks(self, checks) -> None:
        self.registry.register_many(checks)
