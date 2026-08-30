"""
System prompt construction for the natural-language analytics parser.

The prompt is responsible for translating a user's natural-language
analytics question into a structured analytical request.

Important design principles:

1. Metric names are canonical identifiers owned by the metric registry.
2. The LLM must never invent metric identifiers.
3. User language and metric aliases are semantic clues, not output names.
4. Time expressions must be represented deterministically.
5. The LLM extracts intent; it does not generate SQL or numbers.
6. Downstream semantic resolution remains responsible for validating
   the generated analytical request.

This module does not call an LLM and does not execute queries.
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
    """
    Canonical metric information exposed to the LLM.

    The metric registry remains the single source of truth.

    Attributes:
        name:
            Canonical metric identifier. This is the ONLY value that
            may be emitted as `metric` or `additional_metrics`.

        description:
            Business definition of the metric.

        aliases:
            Natural-language expressions users may use to refer to
            the metric. Aliases are semantic clues and must NEVER be
            returned as metric identifiers.

        source_view:
            Analytical source used by the metric. This is used to help
            the LLM avoid combining metrics that cannot belong to the
            same analytical query.
    """

    name: str
    description: str = ""
    aliases: Sequence[str] = field(default_factory=tuple)
    source_view: str = ""

    @classmethod
    def from_definition(
        cls,
        definition: object,
    ) -> "MetricHint":
        """
        Build a MetricHint from a MetricDefinition-like object.

        The function is deliberately duck-typed so this prompt module
        does not need to import the metric registry directly.
        """

        return cls(
            name=definition.name,  # type: ignore[attr-defined]
            description=definition.description,  # type: ignore[attr-defined]
            aliases=tuple(definition.aliases),  # type: ignore[attr-defined]
            source_view=definition.source_view,  # type: ignore[attr-defined]
        )


_RESPONSE_SCHEMA = """\
Respond with exactly one JSON object and nothing else.

Do not return:
- prose
- markdown
- code fences
- explanations
- comments
- SQL
- computed numbers

Use this structure:

{
  "metric": "<canonical metric name>",
  "additional_metrics": ["<canonical metric name>", ...],
  "dimensions": ["<dimension name>", ...],
  "filters": [
    {
      "dimension": "<dimension name>",
      "operator": "<operator>",
      "value": <value>
    }
  ],
  "time_grain": "<known time grain or null>",
  "time_range": null,
  "limit": <integer or null>,
  "sort_by": "<field or null>",
  "sort_order": "<asc, desc, or null>",
  "comparison": {"mode": "<known comparison mode>"} or null
}

When a genuine time constraint exists, use one of these forms.

Relative time:
{
  "preset": "<known preset>",
  "label": null,
  "start": null,
  "end": null
}

Absolute calendar date or period:
{
  "preset": null,
  "label": null,
  "start": "<YYYY-MM-DD>",
  "end": "<YYYY-MM-DD>"
}

Unclear or unsupported time expression:
{
  "preset": null,
  "label": "<short time expression>",
  "start": null,
  "end": null
}
"""


def build_system_prompt(
    *,
    metric_hints: Sequence[MetricHint] = (),
    dimension_hints: Sequence[str] = (),
    today: Optional[date] = None,
) -> str:
    """
    Build the system prompt for one NL-query parsing call.

    The supplied metric hints are treated as the canonical metric
    vocabulary available to the parser. The LLM is instructed to
    select canonical metric names rather than inventing identifiers.

    Args:
        metric_hints:
            Canonical metrics from the metric registry.

        dimension_hints:
            Known dimensions available to the analytical system.

        today:
            Date used only to anchor relative-time interpretation.

    Returns:
        Complete system prompt string.
    """

    lines: list[str] = [
        (
            "You are an analytics intent parser. "
            "Your task is to translate a business user's natural-language "
            "analytics question into one structured analytical request."
        ),
        "",
        (
            "You extract analytical intent only. "
            "You do NOT answer the question, calculate numbers, "
            "generate SQL, inspect the database, or invent database "
            "objects."
        ),
        "",
        (
            "The structured request will be validated by a downstream "
            "analytics system. Accuracy and adherence to the supplied "
            "canonical vocabulary are more important than creativity."
        ),
        "",
    ]

    if today is not None:
        lines.extend(
            [
                f"Today's date is {today.isoformat()}.",
                "",
            ]
        )

    lines.extend(
        [
            _RESPONSE_SCHEMA,
            "",
            "VALID ENUMERATION VALUES",
            "-------------------------",
            (
                "Known time_grain values: "
                + ", ".join(sorted(KNOWN_TIME_GRAINS))
            ),
            (
                "Known time_range.preset values: "
                + ", ".join(sorted(KNOWN_PRESETS))
            ),
            (
                "Known filter operator values: "
                + ", ".join(sorted(KNOWN_FILTER_OPERATORS))
            ),
            (
                "Known comparison.mode values: "
                + ", ".join(sorted(KNOWN_COMPARISON_MODES))
            ),
            "",
        ]
    )

    # ------------------------------------------------------------------
    # Metric selection
    # ------------------------------------------------------------------

    if metric_hints:
        lines.extend(
            [
                "CANONICAL METRIC RULES",
                "-----------------------",
                (
                    "The metric registry below defines the complete "
                    "canonical metric vocabulary available to you."
                ),
                (
                    "`metric` MUST be exactly one of the canonical metric "
                    "names listed below."
                ),
                (
                    "Every value in `additional_metrics` MUST also be "
                    "exactly one of the canonical metric names listed below."
                ),
                (
                    "NEVER invent a metric identifier."
                ),
                (
                    "NEVER rename a metric."
                ),
                (
                    "NEVER pluralize or singularize a metric name."
                ),
                (
                    "NEVER convert the user's wording into a new "
                    "snake_case metric identifier."
                ),
                (
                    "NEVER use a natural-language alias as the output "
                    "metric identifier."
                ),
                (
                    "Natural-language phrases and aliases are clues for "
                    "selecting a canonical metric. They are NOT valid "
                    "metric identifiers."
                ),
                "",
                (
                    "For example, if the canonical metric is `cash_in`, "
                    "the user may say 'cash came in', 'cash inflow', "
                    "'cash received', or 'money came into the business'. "
                    "All of these must map to the canonical metric "
                    "`cash_in`."
                ),
                "",
                (
                    "If no available canonical metric correctly represents "
                    "the user's request, do NOT invent a new metric name. "
                    "Preserve the unsupported/invalid intent so that the "
                    "downstream system can reject it appropriately."
                ),
                "",
                "CANONICAL METRIC CATALOG",
                "------------------------",
            ]
        )

        grouped: dict[str, list[MetricHint]] = {}
        ungrouped: list[MetricHint] = []

        for hint in metric_hints:
            if hint.source_view:
                grouped.setdefault(
                    hint.source_view,
                    [],
                ).append(hint)
            else:
                ungrouped.append(hint)

        def append_metric_hint(hint: MetricHint) -> None:
            lines.append(
                f"  - Canonical metric: `{hint.name}`"
            )

            if hint.description:
                lines.append(
                    f"    Meaning: {hint.description}"
                )

            if hint.aliases:
                lines.append(
                    "    User phrases that may refer to this metric: "
                    + ", ".join(hint.aliases)
                )

            lines.append(
                f"    Output identifier: `{hint.name}`"
            )

        if grouped:
            for source_view, hints in grouped.items():
                lines.append(
                    f"  Source view: `{source_view}`"
                )

                for hint in hints:
                    append_metric_hint(hint)

                lines.append("")

            if ungrouped:
                lines.append(
                    "  Source view: `(unspecified)`"
                )

                for hint in ungrouped:
                    append_metric_hint(hint)

        else:
            for hint in metric_hints:
                append_metric_hint(hint)

        lines.append("")

        # --------------------------------------------------------------
        # Canonical mapping examples
        # --------------------------------------------------------------

        lines.extend(
            [
                "CANONICAL METRIC MAPPING EXAMPLES",
                "---------------------------------",
                (
                    'User: "How much cash came in?" '
                    '→ metric: `cash_in`'
                ),
                (
                    'User: "How much cash went out?" '
                    '→ metric: `cash_out`'
                ),
                (
                    'User: "What is our cash in?" '
                    '→ metric: `cash_in`'
                ),
                (
                    'User: "What is our cash out?" '
                    '→ metric: `cash_out`'
                ),
                (
                    'User: "What are our total payments?" '
                    '→ metric: `total_payments`'
                ),
                (
                    'User: "What are our total expenses?" '
                    '→ metric: `total_expenses`'
                ),
                (
                    'User: "What is our net sales?" '
                    '→ metric: `net_sales`'
                ),
                "",
                (
                    "These examples demonstrate an important rule: "
                    "the user's wording may vary, but the output metric "
                    "identifier must remain canonical."
                ),
                "",
            ]
        )

    # ------------------------------------------------------------------
    # Dimension selection
    # ------------------------------------------------------------------

    if dimension_hints:
        lines.extend(
            [
                "DIMENSION RULES",
                "---------------",
                (
                    "Dimensions may be used for grouping or filtering "
                    "only when they correspond to a known dimension."
                ),
                (
                    "Use the canonical dimension name supplied below."
                ),
                (
                    "Do not invent dimensions or convert user wording "
                    "into arbitrary database column names."
                ),
                "",
                "Known dimensions:",
                "  " + ", ".join(dimension_hints),
                "",
            ]
        )

    # ------------------------------------------------------------------
    # Time range rules
    # ------------------------------------------------------------------

    lines.extend(
        [
            "TIME RANGE RULES",
            "----------------",
            (
                "1. No time constraint:"
            ),
            (
                "   If the user does not express any temporal meaning, "
                "set `time_range` to null."
            ),
            (
                "   Do NOT invent today, current month, current year, "
                "all time, or another default period."
            ),
            "",
            (
                "2. Time grain only:"
            ),
            (
                "   Phrases such as 'by day', 'by week', 'by month', "
                "or 'monthly' set `time_grain`."
            ),
            (
                "   A time grain by itself does NOT create a time range."
            ),
            "",
            (
                "3. Relative time:"
            ),
            (
                "   For expressions such as 'today', 'yesterday', "
                "'this week', 'last week', 'this month', 'last month', "
                "'this quarter', 'this year', 'last 30 days', etc., "
                "use the corresponding known preset."
            ),
            (
                "   Do NOT calculate explicit dates for relative "
                "expressions."
            ),
            "",
            (
                "4. Absolute time:"
            ),
            (
                "   For an unambiguous date or calendar period such as "
                "'2026-08-15', 'January 2026', or 'Q1 2026', return "
                "explicit ISO start/end dates."
            ),
            "",
            (
                "5. Unsupported or unclear time:"
            ),
            (
                "   If the user gives a genuine time expression that "
                "cannot confidently be mapped to a known preset or "
                "absolute dates, put the original short expression "
                "in `time_range.label`."
            ),
            "",
            (
                "NEVER return an empty `{}` time_range object."
            ),
            (
                "NEVER return a time_range object where preset, label, "
                "start, and end are all null."
            ),
            "",
        ]
    )

    # ------------------------------------------------------------------
    # Filter rules
    # ------------------------------------------------------------------

    lines.extend(
        [
            "FILTER RULES",
            "------------",
            (
                "A filter must contain a real dimension, a valid "
                "operator, and the value requested by the user."
            ),
            (
                "Use the canonical dimension name whenever one is known."
            ),
            (
                "Do not use a metric name as a filter dimension unless "
                "the analytical schema explicitly defines it as such."
            ),
            (
                "Do not invent filter dimensions."
            ),
            (
                "Use only the known filter operator values listed above."
            ),
            "",
        ]
    )

    # ------------------------------------------------------------------
    # Multi-metric rules
    # ------------------------------------------------------------------

    lines.extend(
        [
            "MULTI-METRIC RULES",
            "------------------",
            (
                "Use `additional_metrics` only when the user explicitly "
                "requests multiple metrics."
            ),
            (
                "Every requested metric must use its canonical registry "
                "name."
            ),
            (
                "If source-view information is supplied above, metrics "
                "should only be combined when they belong to the same "
                "analytical source."
            ),
            (
                "Do NOT invent a combined metric such as "
                "`sales_and_expenses`."
            ),
            (
                "Do NOT transform two existing metrics into a new metric."
            ),
            (
                "If the requested metrics cannot be represented as one "
                "supported analytical request, preserve the primary "
                "metric and do not invent a workaround."
            ),
            "",
        ]
    )

    # ------------------------------------------------------------------
    # Ambiguity / unsupported requests
    # ------------------------------------------------------------------

    lines.extend(
        [
            "AMBIGUOUS OR UNSUPPORTED REQUESTS",
            "---------------------------------",
            (
                "Do not force an arbitrary metric onto an ambiguous "
                "question."
            ),
            (
                "Do not select a metric merely because it is vaguely "
                "related to the user's words."
            ),
            (
                "Do not invent metrics for requests such as forecasting, "
                "prediction, or unsupported business concepts."
            ),
            (
                "If no canonical metric clearly matches the user's "
                "analytical intent, do not create a new metric identifier."
            ),
            "",
        ]
    )

    # ------------------------------------------------------------------
    # Examples
    # ------------------------------------------------------------------

    lines.extend(
        [
            "STRUCTURED OUTPUT EXAMPLES",
            "---------------------------",
            "",
            'Question: "What are our total expenses?"',
            (
                '{"metric": "total_expenses", '
                '"additional_metrics": [], '
                '"dimensions": [], '
                '"filters": [], '
                '"time_grain": null, '
                '"time_range": null, '
                '"limit": null, '
                '"sort_by": null, '
                '"sort_order": null, '
                '"comparison": null}'
            ),
            "",
            'Question: "What were our net sales last month?"',
            (
                '{"metric": "net_sales", '
                '"additional_metrics": [], '
                '"dimensions": [], '
                '"filters": [], '
                '"time_grain": null, '
                '"time_range": {'
                '"preset": "last_month", '
                '"label": null, '
                '"start": null, '
                '"end": null'
                '}, '
                '"limit": null, '
                '"sort_by": null, '
                '"sort_order": null, '
                '"comparison": null}'
            ),
            "",
            'Question: "What were our net sales in January 2026?"',
            (
                '{"metric": "net_sales", '
                '"additional_metrics": [], '
                '"dimensions": [], '
                '"filters": [], '
                '"time_grain": null, '
                '"time_range": {'
                '"preset": null, '
                '"label": null, '
                '"start": "2026-01-01", '
                '"end": "2026-01-31"'
                '}, '
                '"limit": null, '
                '"sort_by": null, '
                '"sort_order": null, '
                '"comparison": null}'
            ),
            "",
            'Question: "How much cash came in today?"',
            (
                '{"metric": "cash_in", '
                '"additional_metrics": [], '
                '"dimensions": [], '
                '"filters": [], '
                '"time_grain": null, '
                '"time_range": {'
                '"preset": "today", '
                '"label": null, '
                '"start": null, '
                '"end": null'
                '}, '
                '"limit": null, '
                '"sort_by": null, '
                '"sort_order": null, '
                '"comparison": null}'
            ),
            "",
        ]
    )

    # ------------------------------------------------------------------
    # Final validation instruction
    # ------------------------------------------------------------------

    lines.extend(
        [
            "FINAL SELF-CHECK BEFORE RESPONDING",
            "-----------------------------------",
            (
                "Before returning the JSON, silently verify every field."
            ),
            (
                "1. Is `metric` an EXACT canonical metric name from the "
                "catalog?"
            ),
            (
                "2. Is every `additional_metrics` value an EXACT "
                "canonical metric name from the catalog?"
            ),
            (
                "3. Did you accidentally turn an alias or user phrase "
                "into a new metric identifier?"
            ),
            (
                "4. Are all dimensions canonical and supported?"
            ),
            (
                "5. Are all filter operators valid?"
            ),
            (
                "6. Is `time_range` either null or a valid non-empty "
                "time-range object?"
            ),
            (
                "7. Did you avoid inventing a default time range?"
            ),
            (
                "8. Did you avoid inventing SQL, numbers, tables, "
                "columns, or metrics?"
            ),
            "",
            (
                "If a generated metric is not an exact member of the "
                "canonical metric catalog, replace it with the correct "
                "canonical metric or leave the request unsupported. "
                "NEVER return the invented metric."
            ),
            "",
            "Return ONLY the JSON object.",
        ]
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
"EvaluationReport(total_cases=61, passed_cases=44, failed_cases=17, accuracy=72.13, by_category={'dimension': EvaluationBreakdown(total=10, passed=8, failed=2, accuracy=80.0), 'direct_metric': EvaluationBreakdown(total=12, passed=12, failed=0, accuracy=100.0), 'filter': EvaluationBreakdown(total=9, passed=1, failed=8, accuracy=11.11), 'metric_paraphrase': EvaluationBreakdown(total=14, passed=11, failed=3, accuracy=78.57), 'time_based': EvaluationBreakdown(total=16, passed=12, failed=4, accuracy=75.0)}, by_difficulty={'easy': EvaluationBreakdown(total=21, passed=19, failed=2, accuracy=90.48), 'hard': EvaluationBreakdown(total=4, passed=3, failed=1, accuracy=75.0), 'medium': EvaluationBreakdown(total=36, passed=22, failed=14, accuracy=61.11)}, pipeline_failures=0, unexpected_errors=0, failed_case_ids=('EVAL-023', 'EVAL-024', 'EVAL-026', 'EVAL-027', 'EVAL-028', 'EVAL-034', 'EVAL-035', 'EVAL-052', 'EVAL-053', 'EVAL-054', 'EVAL-055', 'EVAL-056', 'EVAL-057', 'EVAL-058', 'EVAL-091', 'EVAL-093', 'EVAL-094'))"

======================================================================
FAILURE ANALYSIS
======================================================================
{
  "total_results": 61,
  "failed_results": 17,
  "failure_counts": {
    "pipeline_failure": 13,
    "metric_mismatch": 4
  },
  "failures": [
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
      "error": "Semantic resolution failed (1 issue(s)): metric: Could not resolve metric value 'total_investment'."
    },
    {
      "case_id": "EVAL-024",
      "question": "How much money was withdrawn?",
      "category": "metric_paraphrase",
      "difficulty": "medium",
      "failure_types": [
        "pipeline_failure"
      ],
      "field_diffs": [],
      "actual_failed_stage": "semantic_resolution",
      "expected_failed_stage": null,
      "error": "Semantic resolution failed (1 issue(s)): metric: Could not resolve metric value 'withdrawn_amount'."
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
      "case_id": "EVAL-027",
      "question": "What were our sales today?",
      "category": "time_based",
      "difficulty": "easy",
      "failure_types": [
        "metric_mismatch"
      ],
      "field_diffs": [
        {
          "field": "metrics",
          "expected": [
            "gross_sales"
          ],
          "actual": [
            "net_sales"
          ]
        }
      ],
      "actual_failed_stage": null,
      "expected_failed_stage": null,
      "error": null
    },
    {
      "case_id": "EVAL-028",
      "question": "What were our sales yesterday?",
      "category": "time_based",
      "difficulty": "easy",
      "failure_types": [
        "metric_mismatch"
      ],
      "field_diffs": [
        {
          "field": "metrics",
          "expected": [
            "gross_sales"
          ],
          "actual": [
            "net_sales"
          ]
        }
      ],
      "actual_failed_stage": null,
      "expected_failed_stage": null,
      "error": null
    },
    {
      "case_id": "EVAL-034",
      "question": "What were our quarterly sales?",
      "category": "time_based",
      "difficulty": "medium",
      "failure_types": [
        "metric_mismatch"
      ],
      "field_diffs": [
        {
          "field": "metrics",
          "expected": [
            "gross_sales"
          ],
          "actual": [
            "net_sales"
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
      "error": "Semantic resolution failed (1 issue(s)): filter:total_expenses: Could not resolve filter:total_expenses value 'total_expenses'."
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
      "actual_failed_stage": "semantic_resolution",
      "expected_failed_stage": null,
      "error": "Semantic resolution failed (1 issue(s)): filter:return_status: Could not resolve filter:return_status value 'return_status'."
    }
  ]
}

======================================================================
EVALUATION COMPLETE
======================================================================
'''