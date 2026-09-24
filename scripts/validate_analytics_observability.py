"""
Interactive validation script for the AI Business Intelligence system.

Usage:
    python -m scripts.validate_analytics_observability

The script:
    1. Accepts a natural-language analytical question.
    2. Resets the in-memory observability metrics.
    3. Executes the real AnalyticsApplication.
    4. Prints the analytical response.
    5. Prints a formatted observability and performance report.

This is a development/validation utility, not a production API.
"""

from __future__ import annotations

import json
from pprint import pprint

from etl.analytics.application.factory import create_analytics_application
from etl.analytics.config.settings import get_settings
from etl.observability.metrics import metrics


def print_section(title: str) -> None:
    """Print a readable section heading."""
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def format_field_name(field: str) -> str:
    """Convert a snake_case field name into a readable label."""
    return field.replace("_", " ").title()


def format_list(values) -> str:
    """Format a list for human-readable output."""
    if not values:
        return "None"

    return ", ".join(str(value) for value in values)


def print_response(response) -> None:
    """Print a human-readable analytical response."""
    print_section("ANALYTICAL ANSWER")

    # --------------------------------------------------------------
    # Status
    # --------------------------------------------------------------

    status = getattr(response, "status", None)
    success = getattr(response, "success", False)

    if success:
        status_text = "SUCCESS"
    else:
        status_text = str(status).upper() if status else "FAILED"

    print(f"Status: {status_text}")

    # --------------------------------------------------------------
    # Error
    # --------------------------------------------------------------

    error = getattr(response, "error", None)

    if error:
        print()
        print("Error")
        print("-----")
        print(error)

    # --------------------------------------------------------------
    # Analytical data
    # --------------------------------------------------------------

    data = getattr(response, "data", None)

    if data:
        print()
        print("Answer")
        print("------")

        for row in data:
            if hasattr(row, "items"):
                for field, value in row.items():
                    label = format_field_name(field)
                    print(f"{label + ':':<20}{value}")
            else:
                print(row)

    else:
        print()
        print("Answer")
        print("------")
        print("No data returned.")

    # --------------------------------------------------------------
    # Query context
    # --------------------------------------------------------------

    query = getattr(response, "query", None)

    if query:
        print()
        print("Query")
        print("-----")

        metrics_list = getattr(query, "metrics", [])
        dimensions = getattr(query, "dimensions", [])
        filters = getattr(query, "filters", [])
        time_grain = getattr(query, "time_grain", None)

        print(
            f"{'Metrics:':<20}"
            f"{format_list(metrics_list)}"
        )

        print(
            f"{'Dimensions:':<20}"
            f"{format_list(dimensions)}"
        )

        print(
            f"{'Filters:':<20}"
            f"{format_list(filters)}"
        )

        print(
            f"{'Time grain:':<20}"
            f"{time_grain or 'None'}"
        )

    # --------------------------------------------------------------
    # Metadata
    # --------------------------------------------------------------

    metadata = getattr(response, "metadata", None)

    if metadata:
        row_count = getattr(metadata, "row_count", None)

        if row_count is not None:
            print()
            print(f"{'Rows:':<20}{row_count}")


def get_timing(
    timings,
    name: str,
    label_key: str | None = None,
    label_value: str | None = None,
) -> float:
    """Return the total duration for a timing metric."""
    for key, metric in timings.items():
        if f"'name': '{name}'" not in key:
            continue

        if label_key is None:
            return metric["total_ms"]

        if f"'{label_key}': '{label_value}'" in key:
            return metric["total_ms"]

    return 0.0


def get_llm_model(timings) -> str:
    """Extract the LLM model name from the timing metric labels."""
    for key in timings:
        if "'name': 'llm_duration_ms'" not in key:
            continue

        marker = "'model': '"

        if marker not in key:
            continue

        start = key.index(marker) + len(marker)
        end = key.index("'", start)

        return key[start:end]

    return "unknown"


def print_performance_report(snapshot) -> None:
    """Print a human-readable observability and performance report."""
    counters = snapshot["counters"]
    totals = snapshot["totals"]
    timings = snapshot["timings"]

    # ------------------------------------------------------------------
    # Pipeline timings
    # ------------------------------------------------------------------

    total_duration = get_timing(
        timings,
        "analytics_query_duration_ms",
    )

    parsing = get_timing(
        timings,
        "analytics_stage_duration_ms",
        "stage",
        "parsing",
    )

    semantic = get_timing(
        timings,
        "analytics_stage_duration_ms",
        "stage",
        "semantic_resolution",
    )

    time_resolution = get_timing(
        timings,
        "analytics_stage_duration_ms",
        "stage",
        "time_resolution",
    )

    orchestration = get_timing(
        timings,
        "analytics_stage_duration_ms",
        "stage",
        "orchestration",
    )

    response = get_timing(
        timings,
        "analytics_stage_duration_ms",
        "stage",
        "response_building",
    )

    # ------------------------------------------------------------------
    # Database metrics
    # ------------------------------------------------------------------

    db_duration = get_timing(
        timings,
        "db_query_duration_ms",
    )

    db_queries = counters.get(
        "db_queries_total",
        0,
    )

    db_successful = counters.get(
        "db_queries_successful",
        0,
    )

    db_rows = totals.get(
        "db_rows_returned",
        0,
    )

    # ------------------------------------------------------------------
    # LLM metrics
    # ------------------------------------------------------------------

    llm_duration = get_timing(
        timings,
        "llm_duration_ms",
    )

    llm_model = get_llm_model(timings)

    llm_requests = counters.get(
        "llm_requests_total",
        0,
    )

    llm_attempts = counters.get(
        "llm_attempts_total",
        0,
    )

    llm_input_tokens = totals.get(
        "llm_input_tokens",
        0,
    )

    llm_output_tokens = totals.get(
        "llm_output_tokens",
        0,
    )

    llm_total_tokens = totals.get(
        "llm_total_tokens",
        0,
    )

    llm_estimated_cost = totals.get(
        "llm_estimated_cost",
        0.0,
    )

    # ------------------------------------------------------------------
    # Report
    # ------------------------------------------------------------------

    print_section("PERFORMANCE REPORT")

    print("Pipeline")
    print("--------")
    print(f"{'Total:':<20}{total_duration:.2f} ms")

    print()
    print("Stages")
    print("------")
    print(f"{'Parsing:':<20}{parsing:.2f} ms")
    print(f"{'Semantic:':<20}{semantic:.2f} ms")
    print(f"{'Time resolution:':<20}{time_resolution:.2f} ms")
    print(f"{'Orchestration:':<20}{orchestration:.2f} ms")
    print(f"{'Response:':<20}{response:.2f} ms")

    print()
    print("Database")
    print("--------")
    print(f"{'Queries:':<20}{db_queries}")
    print(f"{'Successful:':<20}{db_successful}")
    print(f"{'Rows returned:':<20}{db_rows}")
    print(f"{'Duration:':<20}{db_duration:.2f} ms")

    print()
    print("LLM")
    print("---")
    print(f"{'Model:':<20}{llm_model}")
    print(f"{'Requests:':<20}{llm_requests}")
    print(f"{'Attempts:':<20}{llm_attempts}")
    print(f"{'Input tokens:':<20}{llm_input_tokens}")
    print(f"{'Output tokens:':<20}{llm_output_tokens}")
    print(f"{'Total tokens:':<20}{llm_total_tokens}")
    print(f"{'Duration:':<20}{llm_duration:.2f} ms")
    print(f"{'Estimated cost:':<20}{llm_estimated_cost:.6f}৳")


def run_query(
    question: str,
    application,
) -> None:
    """Execute one analytical query and print its performance report."""
    # Reset metrics so this report represents this query only.
    metrics.reset()

    try:
        response = application.query(question)

    except Exception:
        print_section("QUERY FAILED")

        snapshot = metrics.snapshot()
        print_performance_report(snapshot)

        raise

    print_response(response)

    snapshot = metrics.snapshot()
    print_performance_report(snapshot)


def main() -> None:
    """Run the interactive validation loop."""
    print("=" * 72)
    print("AI-BI ANALYTICS + OBSERVABILITY VALIDATION")
    print("=" * 72)
    print("Enter a natural-language analytical question.")
    print("Type 'exit' or 'quit' to stop.")

    settings = get_settings()

    application = create_analytics_application(
        settings=settings,
    )

    while True:
        print()

        try:
            question = input("Question: ").strip()

        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not question:
            continue

        if question.lower() in {"exit", "quit"}:
            break

        run_query(
            question,
            application=application,
        )


if __name__ == "__main__":
    main()