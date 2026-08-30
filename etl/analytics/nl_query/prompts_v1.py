"""
System prompt construction.

Kept separate from parser.py so the prompt text can be read, reviewed,
and iterated on without touching the plumbing code that calls the LLM
and parses its response.

Nothing here calls an LLM or touches the metric registry. It only
builds a string.
"""

from __future__ import annotations

from dataclasses import dataclass, field
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
    so it can map user language onto a real, known metric name.

    `aliases` should be sourced from the metric registry's own
    `MetricDefinition.aliases` wherever possible, so the prompt and
    the registry never drift apart -- the registry stays the single
    source of truth for "what do users call this metric".

    `source_view` is optional grounding about which analytical view
    the metric is computed from. It lets the prompt tell the LLM
    which metrics can plausibly be requested together in one query
    (see the multi-metric rule below). Leave it empty if you don't
    want to expose this yet.

    This is still a HINT, not a validated allowlist: the parser never
    checks the LLM's output against it. Phase 9.3 remains the only
    place that confirms a `metric` value is real. What changed is
    that the prompt now tells the LLM to prefer one of these exact
    names rather than inventing its own."""

    name: str
    description: str = ""
    aliases: Sequence[str] = field(default_factory=tuple)
    source_view: str = ""

    @classmethod
    def from_definition(cls, definition: object) -> "MetricHint":
        """Build a MetricHint from an etl.analytics.metrics.definitions
        .MetricDefinition (or anything else with the same four
        attributes) without this module importing the metrics
        package.

        This is the one place a MetricDefinition's `description`,
        `aliases`, and `source_view` get copied into prompt-facing
        grounding data -- callers should always go through here
        rather than hand-assembling MetricHint(...) themselves, so
        the registry stays the single source of truth for both and
        the two can't drift apart. Deliberately duck-typed (reads
        attributes rather than importing MetricDefinition) to respect
        this module's independence from etl.analytics.metrics --
        see parser.py's module docstring.

        Usage (typically in whatever wires up ParserConfig, e.g. a
        Phase 9.3 orchestration module):

            from etl.analytics.metrics.registry import list_metrics
            from etl.analytics.nl_query.prompts import MetricHint

            metric_hints = tuple(
                MetricHint.from_definition(d) for d in list_metrics()
            )
        """
        return cls(
            name=definition.name, # type: ignore
            description=definition.description, # type: ignore
            aliases=tuple(definition.aliases), # type: ignore
            source_view=definition.source_view, # type: ignore
        )


_RESPONSE_SCHEMA = """\
Respond with exactly one JSON object and nothing else: no prose, no
markdown code fences, no explanation before or after it.

Use this top-level shape. `metric` is required. All other fields are
optional; if you include an optional field that does not apply, set it
to null or an empty array as appropriate. Never use empty placeholder
objects.

{
  "metric": "<string, REQUIRED>",
  "additional_metrics": ["<string>", ...],
  "dimensions": ["<string>", ...],
  "filters": [
    {"dimension": "<string>", "operator": "<string>", "value": <any>}
  ],
  "time_grain": "<string or null>",
  "time_range": null,
  "limit": <integer or null>,
  "sort_by": "<string or null>",
  "sort_order": "<'asc', 'desc', or null>",
  "comparison": {"mode": "<string>"} or null
}

When a genuine time constraint exists, replace `"time_range": null`
with exactly one of these valid objects:

Relative time:
{"preset": "<known preset>", "label": null, "start": null, "end": null}

Absolute calendar date or period:
{"preset": null, "label": null, "start": "<YYYY-MM-DD or null>", "end": "<YYYY-MM-DD or null>"}

Unclear or unsupported time expression:
{"preset": null, "label": "<short time expression>", "start": null, "end": null}"""


def build_system_prompt(
    *,
    metric_hints: Sequence[MetricHint] = (),
    dimension_hints: Sequence[str] = (),
    today: Optional[date] = None,
) -> str:
    """
    Build the system prompt for one parse() call.

    `metric_hints`/`dimension_hints` are grounding context -- passing
    the metric catalog's names/descriptions/aliases measurably
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
        "RELATIVE time language): " + ", ".join(sorted(KNOWN_PRESETS))
    )
    lines.append(
        "Known filter operator values: " + ", ".join(sorted(KNOWN_FILTER_OPERATORS))
    )
    lines.append(
        "Known comparison.mode values: " + ", ".join(sorted(KNOWN_COMPARISON_MODES))
    )
    lines.append("")

    lines.append("Time range decision rules:")
    lines.append(
        "1. No time constraint: if the user did not express any temporal "
        "meaning, set `time_range` to null or omit it. Do not invent a "
        "default period such as today, current month, or all time."
    )
    lines.append(
        "2. Time grain only: phrases like 'by day', 'by week', or 'by "
        "month' set `time_grain`; they are not a time range by themselves."
    )
    lines.append(
        "3. Relative time: for 'today', 'yesterday', 'this week', 'last "
        "week', 'this month', 'last month', 'this quarter', 'this year', "
        "'last 30 days', etc., use the matching known preset. Map 'this "
        "week/month/quarter/year' to current_week/current_month/"
        "current_quarter/current_year. Do not compute start/end dates for "
        "relative language."
    )
    lines.append(
        "4. Absolute time: for an unambiguous calendar date or period "
        "such as '2026-08-15', 'January 2026', or 'Q1 2026', return "
        "explicit ISO start/end dates and keep preset and label null."
    )
    lines.append(
        "5. Unclear time: use `time_range.label` only when the question "
        "contains a real time expression that you cannot confidently map "
        "to a known preset or explicit dates."
    )
    lines.append(
        "Never return `{}` for `time_range`. Never return a `time_range` "
        "object where preset, label, start, and end are all null."
    )
    lines.append("")

    lines.append("Examples:")
    lines.append(
        'Question: "What are our total expenses?"'
    )
    lines.append(
        '{"metric": "total_expenses", "additional_metrics": [], '
        '"dimensions": [], "filters": [], "time_grain": null, '
        '"time_range": null, "limit": null, "sort_by": null, '
        '"sort_order": null, "comparison": null}'
    )
    lines.append("")
    lines.append(
        'Question: "What were our net sales last month?"'
    )
    lines.append(
        '{"metric": "net_sales", "additional_metrics": [], '
        '"dimensions": [], "filters": [], "time_grain": null, '
        '"time_range": {"preset": "last_month", "label": null, '
        '"start": null, "end": null}, "limit": null, '
        '"sort_by": null, "sort_order": null, "comparison": null}'
    )
    lines.append("")
    lines.append(
        'Question: "What were our net sales in January 2026?"'
    )
    lines.append(
        '{"metric": "net_sales", "additional_metrics": [], '
        '"dimensions": [], "filters": [], "time_grain": null, '
        '"time_range": {"preset": null, "label": null, '
        '"start": "2026-01-01", "end": "2026-01-31"}, '
        '"limit": null, "sort_by": null, '
        '"sort_order": null, "comparison": null}'
    )
    lines.append("")

    if metric_hints:
        lines.append(
            "METRIC SELECTION — STRICT RULES:"
        )
        lines.append(
            "1. `metric` MUST be exactly one of the canonical metric names "
            "listed below."
        )
        lines.append(
            "2. Every value in `additional_metrics` MUST also be exactly one "
            "of the canonical metric names listed below."
        )
        lines.append(
            "3. NEVER invent, rename, paraphrase, pluralize, or transform a "
            "metric name."
        )
        lines.append(
            "4. User phrases and aliases are semantic clues only. They must "
            "never be returned as metric identifiers."
        )
        lines.append(
            "5. For example, if the canonical metric is `cash_in`, phrases "
            "such as 'cash came in', 'cash inflow', 'cash received', or "
            "'money came into the business' must map to `cash_in` rather than "
            "`cash_inflows`, `cash_received`, or any other identifier."
        )
        lines.append(
            "6. If no available metric correctly represents the user's "
            "request, do NOT invent a metric. Follow the unsupported/invalid "
            "request behavior defined below."
        )
        lines.append("")

        # Group hints by source_view when that information is available,
        # so the LLM can see which metrics live together and can be
        # requested in the same query (see the multi-metric rule below).
        grouped: dict[str, list[MetricHint]] = {}
        ungrouped: list[MetricHint] = []
        for hint in metric_hints:
            if hint.source_view:
                grouped.setdefault(hint.source_view, []).append(hint)
            else:
                ungrouped.append(hint)

        def _append_hint_lines(hint: MetricHint) -> None:
            lines.append(f"  - {hint.name}")
            if hint.description:
                lines.append(f"    Meaning: {hint.description}")
            if hint.aliases:
                lines.append(
                    "    User phrases: " + ", ".join(hint.aliases)
                )

        if grouped:
            lines.append(
                "Available canonical metrics. Select `metric` and "
                "`additional_metrics` ONLY from these names when a "
                "matching metric exists, grouped by the analytical "
                "source each metric comes from:"
            )
            for source_view, hints in grouped.items():
                lines.append(f"  Source: {source_view}")
                for hint in hints:
                    _append_hint_lines(hint)
            if ungrouped:
                lines.append("  Source: (unspecified)")
                for hint in ungrouped:
                    _append_hint_lines(hint)
        else:
            lines.append(
                "Available canonical metrics. Select `metric` and "
                "`additional_metrics` ONLY from these names when a "
                "matching metric exists:"
            )
            for hint in metric_hints:
                _append_hint_lines(hint)
        lines.append("")

    if dimension_hints:
        lines.append("Dimensions you can group or filter by (best guess only):")
        lines.append("  " + ", ".join(dimension_hints))
        lines.append("")

    lines.append(
        "Multi-metric rule: use `additional_metrics` only when the "
        "requested metrics can plausibly be retrieved from the same "
        "analytical source. If metric grouping by source is shown "
        "above, only combine metrics listed under the SAME source. Do "
        "not combine unrelated metrics into one request merely because "
        "the user mentions both -- if the metrics clearly come from "
        "different parts of the business (e.g. 'sales vs expenses', or "
        "metrics under different sources above), just return the "
        "single metric matching the main intent in `metric` and leave "
        "`additional_metrics` empty; the caller can ask again for the "
        "other one."
    )
    lines.append("")
    lines.append(
        "Never invent SQL, never invent numbers, and never resolve a "
        "metric alias to a database column or table name yourself -- "
        "just extract structure. Return ONLY the JSON object."
    )

    return "\n".join(lines)




'''
======================================================================
ANALYTICS EVALUATION
======================================================================

Loading dataset: D:\\Projects\\LLM Repos\\AI-Business-Intelligence-System\\evaluation\\datasets\\analytics_eval_v4.json
Loaded 61 evaluation cases.

Running evaluation cases...

======================================================================
EVALUATION REPORT
======================================================================
"EvaluationReport(total_cases=61, passed_cases=45, failed_cases=16, accuracy=73.77, by_category={'dimension': EvaluationBreakdown(total=10, passed=8, failed=2, accuracy=80.0), 'direct_metric': EvaluationBreakdown(total=12, passed=12, failed=0, accuracy=100.0), 'filter': EvaluationBreakdown(total=9, passed=1, failed=8, accuracy=11.11), 'metric_paraphrase': EvaluationBreakdown(total=14, passed=9, failed=5, accuracy=64.29), 'time_based': EvaluationBreakdown(total=16, passed=15, failed=1, accuracy=93.75)}, by_difficulty={'easy': EvaluationBreakdown(total=21, passed=21, failed=0, accuracy=100.0), 'hard': EvaluationBreakdown(total=4, passed=3, failed=1, accuracy=75.0), 'medium': EvaluationBreakdown(total=36, passed=21, failed=15, accuracy=58.33)}, pipeline_failures=0, unexpected_errors=0, failed_case_ids=('EVAL-017', 'EVAL-021', 'EVAL-022', 'EVAL-023', 'EVAL-026', 'EVAL-035', 'EVAL-052', 'EVAL-053', 'EVAL-054', 'EVAL-055', 'EVAL-056', 'EVAL-057', 'EVAL-058', 'EVAL-091', 'EVAL-093', 'EVAL-094'))"

======================================================================
FAILURE ANALYSIS
======================================================================
{
  "total_results": 61,
  "failed_results": 16,
  "failure_counts": {
    "pipeline_failure": 14,
    "metric_mismatch": 2
  },
  "failures": [
    {
      "case_id": "EVAL-017",
      "question": "How much did we earn after returns?",
      "category": "metric_paraphrase",
      "difficulty": "medium",
      "failure_types": [
        "pipeline_failure"
      ],
      "field_diffs": [],
      "actual_failed_stage": "semantic_resolution",
      "expected_failed_stage": null,
      "error": "Semantic resolution failed (1 issue(s)): metric: Could not resolve metric value 'net_revenue_after_returns'."
    },
    {
      "case_id": "EVAL-021",
      "question": "How much money came into the business?",
      "category": "metric_paraphrase",
      "difficulty": "medium",
      "failure_types": [
        "metric_mismatch"
      ],
      "field_diffs": [
        {
          "field": "metrics",
          "expected": [
            "cash_in"
          ],
          "actual": [
            "gross_sales"
          ]
        }
      ],
      "actual_failed_stage": null,
      "expected_failed_stage": null,
      "error": null
    },
    {
      "case_id": "EVAL-022",
      "question": "How much money left the business?",
      "category": "metric_paraphrase",
      "difficulty": "medium",
      "failure_types": [
        "pipeline_failure"
      ],
      "field_diffs": [],
      "actual_failed_stage": "semantic_resolution",
      "expected_failed_stage": null,
      "error": "Semantic resolution failed (1 issue(s)): metric: Could not resolve metric value 'money_out'."
    },
    {
      "case_id": "EVAL-023",
      "question": "How much did investors put into the company?",
      "category": "metric_paraphrase",
      "difficulty": "medium",
      "failure_types": [
        "pipeline_failure"
      ],
      "field_diffs": [],
      "actual_failed_stage": "semantic_resolution",
      "expected_failed_stage": null,
      "error": "Semantic resolution failed (1 issue(s)): metric: Could not resolve metric value 'investment_amount'."
    },
    {
      "case_id": "EVAL-026",
      "question": "What did customers pay us in total?",
      "category": "metric_paraphrase",
      "difficulty": "medium",
      "failure_types": [
        "metric_mismatch"
      ],
      "field_diffs": [
        {
          "field": "metrics",
          "expected": [
            "total_payments"
          ],
          "actual": [
            "gross_sales"
          ]
        }
      ],
      "actual_failed_stage": null,
      "expected_failed_stage": null,
      "error": null
    },
    {
      "case_id": "EVAL-035",
      "question": "Show total sales by year.",
      "category": "time_based",
      "difficulty": "medium",
      "failure_types": [
        "pipeline_failure"
      ],
      "field_diffs": [],
      "actual_failed_stage": "semantic_resolution",
      "expected_failed_stage": null,
      "error": "Semantic resolution failed (1 issue(s)): dimensions[0]: Could not resolve dimensions[0] value 'year'."
    },
    {
      "case_id": "EVAL-052",
      "question": "Show gross sales for card payments.",
      "category": "filter",
      "difficulty": "medium",
      "failure_types": [
        "pipeline_failure"
      ],
      "field_diffs": [],
      "actual_failed_stage": "query_execution",
      "expected_failed_stage": null,
      "error": "column \"payment_method\" does not exist\nLINE 3: WHERE payment_method = 'card'\n              ^\n"
    },
    {
      "case_id": "EVAL-053",
      "question": "Show expenses where amount is above 1000.",
      "category": "filter",
      "difficulty": "medium",
      "failure_types": [
        "pipeline_failure"
      ],
      "field_diffs": [],
      "actual_failed_stage": "query_execution",
      "expected_failed_stage": null,
      "error": "current transaction is aborted, commands ignored until end of transaction block\n"
    },
    {
      "case_id": "EVAL-054",
      "question": "Show expenses where amount is under 500 this month.",
      "category": "filter",
      "difficulty": "medium",
      "failure_types": [
        "pipeline_failure"
      ],
      "field_diffs": [],
      "actual_failed_stage": "query_execution",
      "expected_failed_stage": null,
      "error": "current transaction is aborted, commands ignored until end of transaction block\n"
    },
    {
      "case_id": "EVAL-055",
      "question": "Show total expenses in the rent expense category.",
      "category": "filter",
      "difficulty": "medium",
      "failure_types": [
        "pipeline_failure"
      ],
      "field_diffs": [],
      "actual_failed_stage": "query_execution",
      "expected_failed_stage": null,
      "error": "current transaction is aborted, commands ignored until end of transaction block\n"
    },
    {
      "case_id": "EVAL-056",
      "question": "Show payments by cash this week.",
      "category": "filter",
      "difficulty": "medium",
      "failure_types": [
        "pipeline_failure"
      ],
      "field_diffs": [],
      "actual_failed_stage": "query_execution",
      "expected_failed_stage": null,
      "error": "current transaction is aborted, commands ignored until end of transaction block\n"
    },
    {
      "case_id": "EVAL-057",
      "question": "Show expenses at least 250 in the travel category.",
      "category": "filter",
      "difficulty": "hard",
      "failure_types": [
        "pipeline_failure"
      ],
      "field_diffs": [],
      "actual_failed_stage": "semantic_resolution",
      "expected_failed_stage": null,
      "error": "Semantic resolution failed (2 issue(s)): filter:category: 'category' maps to dimension 'product_category', which isn't supported here. Supported dimensions: ['amount', 'cash_account_id', 'cash_account_name', 'expense_category', 'paid_by']; filter:expenses: Could not resolve filter:expenses value 'expenses'."
    },
    {
      "case_id": "EVAL-058",
      "question": "Show orders from this month.",
      "category": "filter",
      "difficulty": "medium",
      "failure_types": [
        "pipeline_failure"
      ],
      "field_diffs": [],
      "actual_failed_stage": "query_execution",
      "expected_failed_stage": null,
      "error": "current transaction is aborted, commands ignored until end of transaction block\n"
    },
    {
      "case_id": "EVAL-091",
      "question": "Show gross sales by product category.",
      "category": "dimension",
      "difficulty": "medium",
      "failure_types": [
        "pipeline_failure"
      ],
      "field_diffs": [],
      "actual_failed_stage": "query_execution",
      "expected_failed_stage": null,
      "error": "current transaction is aborted, commands ignored until end of transaction block\n"
    },
    {
      "case_id": "EVAL-093",
      "question": "Show total returns by return type.",
      "category": "dimension",
      "difficulty": "medium",
      "failure_types": [
        "pipeline_failure"
      ],
      "field_diffs": [],
      "actual_failed_stage": "query_execution",
      "expected_failed_stage": null,
      "error": "current transaction is aborted, commands ignored until end of transaction block\n"
    },
    {
      "case_id": "EVAL-094",
      "question": "Show returns with status pending.",
      "category": "filter",
      "difficulty": "medium",
      "failure_types": [
        "pipeline_failure"
      ],
      "field_diffs": [],
      "actual_failed_stage": "query_execution",
      "expected_failed_stage": null,
      "error": "current transaction is aborted, commands ignored until end of transaction block\n"
    }
  ]
}

======================================================================
EVALUATION COMPLETE
======================================================================
'''