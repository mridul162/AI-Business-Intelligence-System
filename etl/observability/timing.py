from __future__ import annotations

import logging
from contextlib import contextmanager
from time import perf_counter
from typing import Iterator


@contextmanager
def timed_stage(
    stage: str,
    *,
    logger: logging.Logger,
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