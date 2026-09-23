from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Mapping


@dataclass
class CounterMetric:
    """Mutable counter metric."""

    value: int = 0


@dataclass
class TimingMetric:
    """Aggregated duration metric."""

    count: int = 0
    total_ms: float = 0.0
    min_ms: float | None = None
    max_ms: float | None = None

    def observe(self, duration_ms: float) -> None:
        self.count += 1
        self.total_ms += duration_ms

        if self.min_ms is None or duration_ms < self.min_ms:
            self.min_ms = duration_ms

        if self.max_ms is None or duration_ms > self.max_ms:
            self.max_ms = duration_ms

    @property
    def average_ms(self) -> float:
        if self.count == 0:
            return 0.0

        return self.total_ms / self.count


class MetricsCollector:
    """
    Lightweight in-process metrics collector.

    This is intentionally application-local. It provides basic
    counters and timing aggregation without introducing an external
    metrics backend.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._counters: dict[str, CounterMetric] = {}
        self._timings: dict[tuple[str, tuple[tuple[str, str], ...]], TimingMetric] = {}

    def increment(
        self,
        name: str,
        *,
        labels: Mapping[str, object] | None = None,
    ) -> None:
        del labels  # Labels are not needed for counters yet.

        with self._lock:
            metric = self._counters.setdefault(
                name,
                CounterMetric(),
            )
            metric.value += 1

    def observe(
        self,
        name: str,
        value_ms: float,
        *,
        labels: Mapping[str, object] | None = None,
    ) -> None:
        normalized_labels = tuple(
            sorted(
                (key, str(value))
                for key, value in (labels or {}).items()
            )
        )

        key = (name, normalized_labels)

        with self._lock:
            metric = self._timings.setdefault(
                key,
                TimingMetric(),
            )
            metric.observe(value_ms)

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            counters = {
                name: metric.value
                for name, metric in self._counters.items()
            }

            timings = {}

            for (name, labels), metric in self._timings.items():
                timing_key = {
                    "name": name,
                    "labels": dict(labels),
                }

                timings_key = str(timing_key)

                timings[timings_key] = {
                    "count": metric.count,
                    "total_ms": metric.total_ms,
                    "average_ms": metric.average_ms,
                    "min_ms": metric.min_ms,
                    "max_ms": metric.max_ms,
                }

            return {
                "counters": counters,
                "timings": timings,
            }

    def reset(self) -> None:
        with self._lock:
            self._counters.clear()
            self._timings.clear()


metrics = MetricsCollector()