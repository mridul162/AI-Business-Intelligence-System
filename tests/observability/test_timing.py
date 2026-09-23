from __future__ import annotations

import logging

import pytest

from etl.observability.timing import timed_stage

from etl.observability.metrics import MetricsCollector


def test_timed_stage_logs_duration(caplog):
    logger = logging.getLogger("test.timing")

    with caplog.at_level(logging.INFO, logger="test.timing"):
        with timed_stage("test_stage", logger=logger):
            pass

    record = next(
        record
        for record in caplog.records
        if "analytics_stage_completed" in record.message
    )

    assert "stage=test_stage" in record.message
    assert "duration_ms=" in record.message
    assert "status=success" in record.message


def test_timed_stage_logs_failure_and_reraises(caplog):
    logger = logging.getLogger("test.timing")

    with caplog.at_level(logging.INFO, logger="test.timing"):
        with pytest.raises(ValueError, match="boom"):
            with timed_stage("failing_stage", logger=logger):
                raise ValueError("boom")

    record = next(
        record
        for record in caplog.records
        if "analytics_stage_completed" in record.message
    )

    assert "stage=failing_stage" in record.message
    assert "duration_ms=" in record.message


def test_timed_stage_records_metrics() -> None:
    metrics = MetricsCollector()
    logger = logging.getLogger("test.timing")

    with timed_stage(
        "parsing",
        logger=logger,
        metrics=metrics,
    ):
        pass

    snapshot = metrics.snapshot()

    timing = next(
        value 
        for key, value in snapshot["timings"].items() # type: ignore 
        if "parsing" in key
    )

    assert timing["count"] == 1
    assert timing["total_ms"] >= 0
    assert timing["min_ms"] >= 0
    assert timing["max_ms"] >= 0