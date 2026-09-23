from __future__ import annotations

import logging
from contextlib import contextmanager
from time import perf_counter
from typing import Iterator

from etl.observability.metrics import MetricsCollector


@contextmanager
def timed_stage(
    stage: str,
    *,
    logger: logging.Logger,
    metrics: MetricsCollector | None = None,
    **fields: object,
) -> Iterator[None]:
    """Measure and log the duration of one application stage."""

    started_at = perf_counter()
    status = "success"

    try:
        yield
    except Exception:
        status = "failed"
        raise
    finally:
        duration_ms = (perf_counter() - started_at) * 1000

        if metrics is not None:
            metrics.observe(
                "analytics_stage_duration_ms",
                duration_ms,
                labels={"stage": stage},
            )

        extra_fields = " ".join(
            f"{key}={value}" for key, value in fields.items()
        )

        message = (
            f"analytics_stage_completed "
            f"stage={stage} "
            f"duration_ms={duration_ms:.2f} "
            f"status={status}"
        )

        if extra_fields:
            message = f"{message} {extra_fields}"

        logger.info(message)