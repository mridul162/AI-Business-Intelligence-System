from etl.observability.metrics import MetricsCollector


def test_increment_counter() -> None:
    metrics = MetricsCollector()

    metrics.increment("analytics_queries_total")
    metrics.increment("analytics_queries_total")

    snapshot = metrics.snapshot()

    assert snapshot["counters"]["analytics_queries_total"] == 2 # type: ignore


def test_observe_timing() -> None:
    metrics = MetricsCollector()

    metrics.observe(
        "analytics_stage_duration_ms",
        10.0,
        labels={"stage": "parsing"},
    )
    metrics.observe(
        "analytics_stage_duration_ms",
        30.0,
        labels={"stage": "parsing"},
    )

    snapshot = metrics.snapshot()

    timing = next(
        value
        for key, value in snapshot["timings"].items() # type: ignore
        if "parsing" in key
    )

    assert timing["count"] == 2
    assert timing["total_ms"] == 40.0
    assert timing["average_ms"] == 20.0
    assert timing["min_ms"] == 10.0
    assert timing["max_ms"] == 30.0


def test_different_labels_are_tracked_separately() -> None:
    metrics = MetricsCollector()

    metrics.observe(
        "analytics_stage_duration_ms",
        10.0,
        labels={"stage": "parsing"},
    )
    metrics.observe(
        "analytics_stage_duration_ms",
        50.0,
        labels={"stage": "database_execution"},
    )

    snapshot = metrics.snapshot()

    assert len(snapshot["timings"]) == 2 # type: ignore


def test_reset_clears_metrics() -> None:
    metrics = MetricsCollector()

    metrics.increment("analytics_queries_total")
    metrics.observe(
        "analytics_stage_duration_ms",
        10.0,
        labels={"stage": "parsing"},
    )

    metrics.reset()

    snapshot = metrics.snapshot()

    assert snapshot["counters"] == {}
    assert snapshot["timings"] == {}