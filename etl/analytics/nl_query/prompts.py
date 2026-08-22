"""
Phase 9.2 -- system prompt construction.

Kept separate from parser.py so the prompt text can be read, reviewed,
and iterated on without touching the plumbing code that calls the LLM
and parses its response.

Nothing here calls an LLM or touches the metric registry. It only
builds a string.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional, Sequence

from etl.analytics.schemas import (
    KNOWN_COMPARISON_MODES,
    KNOWN_FILTER_OPERATORS,
    KNOWN_PRESETS,
    KNOWN_TIME_GRAINS,
)


@dataclass(frozen=True)
class MetricHint:
    """One line of grounding context about a metric, shown to the LLM
    so it can make a plausible guess for `metric`/`additional_metrics`.

    This is a HINT, not a validated allowlist: the parser never checks
    the LLM's output against it, and the LLM is free to return a name
    that isn't in this list (e.g. a business term it maps to a metric
    not listed here, or gets wrong). Phase 9.3 is still the only place
    that confirms a `metric` value is real."""

    name: str
    description: str = ""


_RESPONSE_SCHEMA = """\
Respond with a single JSON object and nothing else: no prose, no
markdown code fences, no explanation before or after it. Use this
shape (omit a key, or use null, when it doesn't apply):

{
  "metric": "<string, REQUIRED>",
  "additional_metrics": ["<string>", ...],
  "dimensions": ["<string>", ...],
  "filters": [
    {"dimension": "<string>", "operator": "<string>", "value": <any>}
  ],
  "time_grain": "<string or null>",
  "time_range": {
    "preset": "<string or null>",
    "label": "<string or null>",
    "start": "<YYYY-MM-DD or null>",
    "end": "<YYYY-MM-DD or null>"
  },
  "limit": <integer or null>,
  "sort_by": "<string or null>",
  "sort_order": "<'asc', 'desc', or null>",
  "comparison": {"mode": "<string>"} or null
}"""


def build_system_prompt(
    *,
    metric_hints: Sequence[MetricHint] = (),
    dimension_hints: Sequence[str] = (),
    today: Optional[date] = None,
) -> str:
    """
    Build the system prompt for one parse() call.

    `metric_hints`/`dimension_hints` are optional grounding context --
    passing the metric catalog's names/descriptions measurably
    improves the LLM's guesses, but nothing downstream trusts them:
    the parser doesn't check its own output against these lists.

    `today` anchors relative-date reasoning about WHICH preset applies
    (e.g. telling "this month" apart from "last month"); it is never
    used to compute an actual start/end date here -- that's Phase
    9.4's job.
    """

    lines: list[str] = [
        "You turn a business user's natural-language analytics "
        "question into a single structured JSON object describing "
        "what they want to know. You do not answer the question, "
        "compute numbers, or write SQL -- you only extract structure.",
        "",
    ]

    if today is not None:
        lines.append(f"Today's date is {today.isoformat()}.")
        lines.append("")

    lines.append(_RESPONSE_SCHEMA)
    lines.append("")

    lines.append(
        "Known time_grain values (use exactly one, or null): "
        + ", ".join(sorted(KNOWN_TIME_GRAINS))
    )
    lines.append(
        "Known time_range.preset values (use exactly one, for "
        "RELATIVE time language like 'this month', 'last week', "
        "'today', 'last 30 days'): " + ", ".join(sorted(KNOWN_PRESETS))
    )
    lines.append(
        "Known filter operator values: " + ", ".join(sorted(KNOWN_FILTER_OPERATORS))
    )
    lines.append(
        "Known comparison.mode values: " + ", ".join(sorted(KNOWN_COMPARISON_MODES))
    )
    lines.append("")

    lines.append(
        "Time range rule: if the question names an ABSOLUTE, "
        "unambiguous calendar period (a specific month + year, a "
        "specific date, a specific quarter + year), compute and "
        "return explicit time_range.start / time_range.end dates "
        "yourself. If the question uses RELATIVE language whose "
        "meaning depends on today's date ('this month', 'last week', "
        "'yesterday', 'last 30 days'), return the matching "
        "time_range.preset instead and leave start/end null -- do "
        "not guess actual dates for relative language."
    )
    lines.append(
        "If a time expression doesn't map to a known preset and "
        "isn't an absolute period you can compute with confidence, "
        "put your best short description of it in time_range.label "
        "and leave start/end null."
    )
    lines.append("")

    if metric_hints:
        lines.append(
            "Metrics you can choose `metric` / `additional_metrics` "
            "from (best guess only -- if nothing fits well, still "
            "return your best guess; it will be checked separately):"
        )
        for hint in metric_hints:
            if hint.description:
                lines.append(f"  - {hint.name}: {hint.description}")
            else:
                lines.append(f"  - {hint.name}")
        lines.append("")

    if dimension_hints:
        lines.append("Dimensions you can group or filter by (best guess only):")
        lines.append("  " + ", ".join(dimension_hints))
        lines.append("")

    lines.append(
        "If the question asks about more than one metric that "
        "plausibly share one underlying query (e.g. 'sales and "
        "payments'), put the primary one in `metric` and the rest in "
        "`additional_metrics`. If the metrics clearly come from "
        "different parts of the business (e.g. 'sales vs expenses'), "
        "just return the single metric matching the main intent -- "
        "the caller can ask again for the other one."
    )
    lines.append("")
    lines.append(
        "Never invent SQL, never invent numbers, and never resolve a "
        "metric alias to a database column or table name yourself -- "
        "just extract structure. Return ONLY the JSON object."
    )

    return "\n".join(lines)
