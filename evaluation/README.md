# Evaluation Dataset — `analytics_eval_v1.json`

This is the Phase 10.1 evaluation dataset for the AI Business Intelligence
System: a curated benchmark of realistic business questions with expected
**structured** outputs, used to score the pipeline deterministically
(`expected.metrics == actual.metrics`, etc.) rather than with an LLM judge.

## At a glance

| | |
|---|---|
| Total cases | 78 |
| Success cases | 67 |
| Expected-failure cases | 11 |
| Format | `evaluation/schemas/evaluation_case.py` (`EvaluationCase`) |

### By category

| Category | Count | What it tests |
|---|---|---|
| `direct_metric` | 12 | Canonical metric names/phrasings resolve directly |
| `metric_paraphrase` | 14 | Alias/paraphrase coverage in the parser + semantic resolver |
| `time_based` | 16 | Time expression parsing, time grain vs. time range, and the "no time specified" case |
| `dimension` | 8 | Only dimension combinations the registry actually supports (plus one intentionally unsupported combination) |
| `filter` | 8 | Filter field/operator/value extraction |
| `multi_metric` | 10 | Multiple metrics from a single query |
| `ambiguous_invalid` | 10 | Correct *rejection* of out-of-scope, malformed, or unsupported questions |

## Assumed metric registry

The dataset assumes the following canonical metrics exist. Update
`METRIC_ALIASES` documentation and regenerate the dataset if your actual
registry differs:

```
total_expenses
net_sales
total_sales
total_payments
capital_added
capital_withdrawn
cash_in
cash_out
orders_count
```

## Assumed supported dimensions

Per the Phase 10.1 guidance, only dimension combinations the registry
*actually* supports are tested (testing an unsupported combination would
evaluate a missing feature, not model performance). The dataset assumes:

```
total_payments  -> payment_method
cash_in         -> payment_method
cash_out        -> payment_method
total_expenses  -> category
```

One deliberate exception: `EVAL-047` ("Show net sales by payment method")
asks for `net_sales` broken down by `payment_method`, which is **not** in
the supported list above. This is intentional — it is an
`expected_status: "failure"` case at `semantic_resolution`, testing that
the system correctly rejects an unsupported metric/dimension pairing
instead of silently returning a wrong or empty result.

## Regression cases

The following cases exist specifically to prevent previously-observed
bugs from silently reappearing (see `notes` field on each case):

- `EVAL-001`, `EVAL-025` — `"total expenses"` must resolve to
  `total_expenses`, not `orders` (previously mis-extracted).
- `EVAL-007` — `"How much capital was added?"` regression case from the
  Phase 10 write-up.
- `EVAL-009` — `"How many orders did we receive?"` confirms genuine
  `orders_count` intent still resolves correctly (i.e. the fix for the
  bug above didn't overcorrect).
- `EVAL-029`, `EVAL-030` — no time phrase present at all must resolve to
  `time_range: null`, never an empty `{}` object.

## Structure of one case

```json
{
  "id": "EVAL-001",
  "question": "What are our total expenses?",
  "category": "direct_metric",
  "difficulty": "easy",
  "expected_status": "success",
  "expected": {
    "metrics": ["total_expenses"],
    "dimensions": [],
    "filters": [],
    "time_grain": null,
    "time_range": null
  },
  "expected_failed_stage": null,
  "failure_reason": null,
  "notes": "Regression case: parser previously mis-extracted this as 'orders'."
}
```

Failure cases omit `expected` and instead specify where in the pipeline
the question should be rejected:

```json
{
  "id": "EVAL-069",
  "question": "How is the business doing?",
  "category": "ambiguous_invalid",
  "difficulty": "hard",
  "expected_status": "failure",
  "expected": null,
  "expected_failed_stage": "parser",
  "failure_reason": "No extractable metric, dimension, or time expression; too open-ended to parse.",
  "notes": null
}
```

## Loading the dataset

```python
from evaluation.schemas.evaluation_case import load_dataset

cases = load_dataset("evaluation/datasets/analytics_eval_v1.json")
success_cases = [c for c in cases if c.expected_status.value == "success"]
failure_cases = [c for c in cases if c.expected_status.value == "failure"]
```

## Regenerating

The dataset is generated (and validated for duplicate IDs / required
fields) by `build_dataset.py` at the repo root, rather than hand-edited as
raw JSON. To add cases, add an `add(...)` call there and re-run:

```bash
python3 build_dataset.py
```

## Current evaluation status

Phase 10.1 through Phase 10.4 are implemented:

- **Phase 10.1** — versioned dataset and deterministic expected-output schema.
- **Phase 10.2** — evaluation runner with typed pipeline-stage detection.
- **Phase 10.3** — end-to-end evaluation through `AnalyticsApplication`.
- **Phase 10.4** — failure taxonomy aggregation and field-level diagnostics.
- **Phase 10.5** — Evaluation Baseline & Correctness Hardening

The current taxonomy distinguishes parser, semantic resolution, time
resolution, planning, SQL construction, execution, result merging, and
expected-vs-actual output mismatches. The generic `pipeline_failure` category
is retained for compatibility with older reports.

The next step is correctness hardening: freeze a baseline, select one failure
class, fix the responsible layer, add a regression case, and rerun targeted
tests, the full suite, and the evaluation dataset. Do not modify expected
answers merely to improve the score.

### 10.5.1 — Run and freeze the current baseline

Run the complete evaluation dataset through:

NL Question
    ↓
AnalyticsApplication
    ↓
Evaluation Runner
    ↓
Failure Analyzer
    ↓
Evaluation Report

Record:

Dataset version
Total cases
Passed
Failed
Accuracy
Failure by stage
Failure by category
Failure by difficulty

The important thing is not to optimize the accuracy number blindly.

You want to know:

Which layer is responsible for each failure?

### 10.5.2 — Inspect failures by stage

Your new taxonomy makes this straightforward:

Parser
Semantic Resolution
Time Resolution
Planning
SQL Construction
Execution
Result Merging
Output Mismatch

For every remaining failure:

Evaluation Case
      ↓
Failure Stage
      ↓
Failure Reason
      ↓
Responsible Component
      ↓
Fix
      ↓
Regression Test

This is the point where your evaluation system starts functioning as an actual development feedback loop, rather than just a benchmark.

### 10.5.3 — Add regression cases

Every legitimate correctness bug discovered should produce a permanent test.

For example:

EVAL-035
   ↓
Parser produced invalid dimension
   ↓
Fix parser behavior
   ↓
Add parser regression test
   ↓
Re-run evaluation

But if an evaluation case exposes an intentionally unsupported behavior, don't automatically modify the system to satisfy it. First decide whether:

the implementation is wrong,
the expected output is wrong,
the capability is unsupported,
or the question itself is ambiguous/invalid.

That distinction is important for avoiding evaluation overfitting.

### 10.5.4 — Establish a quality gate

Once the remaining failures have been investigated, introduce a reproducible evaluation command such as:

pytest
python -m etl.analytics.evaluation.run_evaluation

and eventually make the evaluation report provide a clear result like:

Evaluation Baseline
────────────────────────────
Dataset: analytics_eval_vX
Cases:   N
Passed:  N
Failed:  N
Accuracy: XX.XX%

Pipeline failures: N
Output mismatches: N

Status: PASS / REVIEW

The exact threshold should come from your project's requirements rather than choosing an arbitrary percentage.