from __future__ import annotations

from etl.data_quality.models import DataQualityCheck, DataQualityReport, DataQualityResult


class DataQualityRegistry:
    """Register and execute data-quality checks."""

    def __init__(self) -> None:
        self._checks: list[DataQualityCheck] = []

    def register(self, check: DataQualityCheck) -> None:
        self._checks.append(check)

    def register_many(self, checks: list[DataQualityCheck]) -> None:
        self._checks.extend(checks)

    def run(self, session: object) -> DataQualityReport:
        results: list[DataQualityResult] = []

        for check in self._checks:
            result = check.func(session)
            if not isinstance(result, DataQualityResult):
                raise TypeError(
                    f"Check '{check.name}' did not return a DataQualityResult."
                )
            results.append(result)

        return DataQualityReport(checks=results)

    @property
    def checks(self) -> list[DataQualityCheck]:
        return list(self._checks)
