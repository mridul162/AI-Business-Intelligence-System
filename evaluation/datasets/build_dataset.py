"""
Builds evaluation/datasets/analytics_eval_v1.json from a Python literal so
every case is validated by the EvaluationCase dataclass (unique ids,
required fields per status) before being written out.

Assumed metric registry (documented in evaluation/datasets/README.md):
    total_expenses, net_sales, total_sales, total_payments,
    capital_added, capital_withdrawn, cash_in, cash_out, orders_count

Assumed supported dimensions (conservative, per Phase 10.1 guidance to
only test dimensions the registry actually supports):
    total_payments  -> payment_method
    cash_in         -> payment_method
    cash_out        -> payment_method
    total_expenses  -> category
"""

import sys

sys.path.insert(0, "/home/claude")

from evaluation.schemas.evaluation_case import (
    Difficulty as D,
    EvalCategory as C,
    EvaluationCase as Case,
    ExpectedFilter as F,
    ExpectedOutput as E,
    ExpectedStatus as S,
    FailureStage as Stage,
    save_dataset,
    validate_dataset,
)

cases = []
n = 0


def add(question, category, difficulty, expected=None, *, failed_stage=None,
        failure_reason=None, notes=None):
    global n
    n += 1
    cases.append(Case(
        id=f"EVAL-{n:03d}",
        question=question,
        category=category,
        difficulty=difficulty,
        expected_status=S.SUCCESS if expected is not None else S.FAILURE,
        expected=expected,
        expected_failed_stage=failed_stage,
        failure_reason=failure_reason,
        notes=notes,
    ))


# --------------------------------------------------------------------------- #
# Category 1 -- Direct metric queries
# --------------------------------------------------------------------------- #

add("What are our total expenses?", C.DIRECT_METRIC, D.EASY,
    E(metrics=["total_expenses"]),
    notes="Regression case: parser previously mis-extracted this as 'orders'.")

add("What is our net sales?", C.DIRECT_METRIC, D.EASY,
    E(metrics=["net_sales"]))

add("What is our total sales?", C.DIRECT_METRIC, D.EASY,
    E(metrics=["total_sales"]))

add("How much did we receive in payments?", C.DIRECT_METRIC, D.EASY,
    E(metrics=["total_payments"]))

add("How much cash came in?", C.DIRECT_METRIC, D.EASY,
    E(metrics=["cash_in"]))

add("How much cash went out?", C.DIRECT_METRIC, D.EASY,
    E(metrics=["cash_out"]))

add("How much capital was added?", C.DIRECT_METRIC, D.EASY,
    E(metrics=["capital_added"]),
    notes="Regression case from Phase 10 write-up.")

add("How much capital was withdrawn?", C.DIRECT_METRIC, D.EASY,
    E(metrics=["capital_withdrawn"]))

add("How many orders did we receive?", C.DIRECT_METRIC, D.EASY,
    E(metrics=["orders_count"]),
    notes="Regression case: distinguishes genuine 'orders' intent from the expenses->orders bug.")

add("What are our total payments?", C.DIRECT_METRIC, D.EASY,
    E(metrics=["total_payments"]))

add("What is our cash in?", C.DIRECT_METRIC, D.EASY,
    E(metrics=["cash_in"]))

add("What is our cash out?", C.DIRECT_METRIC, D.EASY,
    E(metrics=["cash_out"]))


# --------------------------------------------------------------------------- #
# Category 2 -- Metric paraphrases
# --------------------------------------------------------------------------- #

add("What did we spend?", C.METRIC_PARAPHRASE, D.MEDIUM,
    E(metrics=["total_expenses"]))

add("What were our business expenses?", C.METRIC_PARAPHRASE, D.MEDIUM,
    E(metrics=["total_expenses"]))

add("How much money did the business spend?", C.METRIC_PARAPHRASE, D.MEDIUM,
    E(metrics=["total_expenses"]))

add("What is our expenditure?", C.METRIC_PARAPHRASE, D.MEDIUM,
    E(metrics=["total_expenses"]),
    notes="Tests alias coverage for 'expenditure' -> total_expenses.")

add("How much did we earn after returns?", C.METRIC_PARAPHRASE, D.MEDIUM,
    E(metrics=["net_sales"]))

add("What was our revenue after customer returns?", C.METRIC_PARAPHRASE, D.MEDIUM,
    E(metrics=["net_sales"]))

add("How much did we sell in total?", C.METRIC_PARAPHRASE, D.MEDIUM,
    E(metrics=["total_sales"]))

add("What was our total revenue?", C.METRIC_PARAPHRASE, D.MEDIUM,
    E(metrics=["total_sales"]))

add("How much money came into the business?", C.METRIC_PARAPHRASE, D.MEDIUM,
    E(metrics=["cash_in"]))

add("How much money left the business?", C.METRIC_PARAPHRASE, D.MEDIUM,
    E(metrics=["cash_out"]))

add("How much did investors put into the company?", C.METRIC_PARAPHRASE, D.MEDIUM,
    E(metrics=["capital_added"]))

add("How much money was taken out by owners?", C.METRIC_PARAPHRASE, D.MEDIUM,
    E(metrics=["capital_withdrawn"]))

add("How many purchases did customers make?", C.METRIC_PARAPHRASE, D.MEDIUM,
    E(metrics=["orders_count"]))

add("What did customers pay us in total?", C.METRIC_PARAPHRASE, D.MEDIUM,
    E(metrics=["total_payments"]))


# --------------------------------------------------------------------------- #
# Category 3 -- Time-based questions
# --------------------------------------------------------------------------- #

add("What were our sales today?", C.TIME_BASED, D.EASY,
    E(metrics=["total_sales"], time_range="today"))

add("What were our sales yesterday?", C.TIME_BASED, D.EASY,
    E(metrics=["total_sales"], time_range="yesterday"))

add("Show net sales this week.", C.TIME_BASED, D.EASY,
    E(metrics=["net_sales"], time_range="this_week"))

add("What were net sales last week?", C.TIME_BASED, D.EASY,
    E(metrics=["net_sales"], time_range="last_week"))

add("What were total expenses last month?", C.TIME_BASED, D.EASY,
    E(metrics=["total_expenses"], time_range="last_month"))

add("What are our expenses this month?", C.TIME_BASED, D.EASY,
    E(metrics=["total_expenses"], time_range="this_month"))

add("Show monthly net sales.", C.TIME_BASED, D.MEDIUM,
    E(metrics=["net_sales"], time_grain="monthly"))

add("What were our quarterly sales?", C.TIME_BASED, D.MEDIUM,
    E(metrics=["total_sales"], time_grain="quarterly"))

add("Show total sales by year.", C.TIME_BASED, D.MEDIUM,
    E(metrics=["total_sales"], time_grain="yearly"))

add("Show total expenses by day this month.", C.TIME_BASED, D.MEDIUM,
    E(metrics=["total_expenses"], time_grain="daily", time_range="this_month"))

add("What is our total sales?", C.TIME_BASED, D.EASY,
    E(metrics=["total_sales"], time_range=None),
    notes="No time specified -- must resolve to time_range=None, not an empty {} object.")

add("What are our total expenses?", C.TIME_BASED, D.EASY,
    E(metrics=["total_expenses"], time_range=None),
    notes="Duplicate wording from Category 1, re-tested here to confirm absence of a stray "
          "time_range when no time phrase is present at all.")

add("How much cash came in this quarter?", C.TIME_BASED, D.MEDIUM,
    E(metrics=["cash_in"], time_range="this_quarter"))

add("How much capital was added this year?", C.TIME_BASED, D.MEDIUM,
    E(metrics=["capital_added"], time_range="this_year"))

add("Show weekly net sales for this month.", C.TIME_BASED, D.HARD,
    E(metrics=["net_sales"], time_grain="weekly", time_range="this_month"))

add("What were yesterday's payments?", C.TIME_BASED, D.EASY,
    E(metrics=["total_payments"], time_range="yesterday"))


# --------------------------------------------------------------------------- #
# Category 4 -- Dimensions (only combinations the registry actually supports)
# --------------------------------------------------------------------------- #

add("Show total payments by payment method.", C.DIMENSION, D.MEDIUM,
    E(metrics=["total_payments"], dimensions=["payment_method"]))

add("Break down cash in by payment method.", C.DIMENSION, D.MEDIUM,
    E(metrics=["cash_in"], dimensions=["payment_method"]))

add("Show cash out by payment method.", C.DIMENSION, D.MEDIUM,
    E(metrics=["cash_out"], dimensions=["payment_method"]))

add("Show total expenses by category.", C.DIMENSION, D.MEDIUM,
    E(metrics=["total_expenses"], dimensions=["category"]))

add("Break down this month's expenses by category.", C.DIMENSION, D.MEDIUM,
    E(metrics=["total_expenses"], dimensions=["category"], time_range="this_month"))

add("Show payment method breakdown of total payments this week.", C.DIMENSION, D.MEDIUM,
    E(metrics=["total_payments"], dimensions=["payment_method"], time_range="this_week"))

add("Show net sales by payment method.", C.DIMENSION, D.HARD,
    failed_stage=Stage.SEMANTIC_RESOLUTION,
    failure_reason="net_sales does not support the payment_method dimension in the registry.",
    notes="Intentionally invalid combination -- tests correct rejection, not just correct answers.")

add("Show expenses by month and category.", C.DIMENSION, D.HARD,
    E(metrics=["total_expenses"], dimensions=["category"], time_grain="monthly"))


# --------------------------------------------------------------------------- #
# Category 5 -- Filters
# --------------------------------------------------------------------------- #

add("Show payments for cash.", C.FILTER, D.MEDIUM,
    E(metrics=["total_payments"],
      filters=[F(field="payment_method", operator="=", value="cash")]))

add("Show cash in for card payments.", C.FILTER, D.MEDIUM,
    E(metrics=["cash_in"],
      filters=[F(field="payment_method", operator="=", value="card")]))

add("Show expenses above 1000.", C.FILTER, D.MEDIUM,
    E(metrics=["total_expenses"],
      filters=[F(field="amount", operator=">", value=1000)]))

add("Show expenses under 500 this month.", C.FILTER, D.MEDIUM,
    E(metrics=["total_expenses"],
      filters=[F(field="amount", operator="<", value=500)],
      time_range="this_month"))

add("Show total expenses in the office category.", C.FILTER, D.MEDIUM,
    E(metrics=["total_expenses"],
      filters=[F(field="category", operator="=", value="office")]))

add("Show cash payments received this week.", C.FILTER, D.MEDIUM,
    E(metrics=["total_payments"],
      filters=[F(field="payment_method", operator="=", value="cash")],
      time_range="this_week"))

add("Show expenses at least 250 in the travel category.", C.FILTER, D.HARD,
    E(metrics=["total_expenses"],
      filters=[
          F(field="amount", operator=">=", value=250),
          F(field="category", operator="=", value="travel"),
      ]))

add("Show orders from this month.", C.FILTER, D.MEDIUM,
    E(metrics=["orders_count"], time_range="this_month"),
    notes="Phrased as a filter but 'from this month' resolves to a time_range, not a filter clause.")


# --------------------------------------------------------------------------- #
# Category 6 -- Multi-metric queries
# --------------------------------------------------------------------------- #

add("Compare total sales and total expenses.", C.MULTI_METRIC, D.MEDIUM,
    E(metrics=["total_sales", "total_expenses"]))

add("Show net sales and total payments.", C.MULTI_METRIC, D.MEDIUM,
    E(metrics=["net_sales", "total_payments"]))

add("Show cash in and cash out.", C.MULTI_METRIC, D.MEDIUM,
    E(metrics=["cash_in", "cash_out"]))

add("How much capital was added and withdrawn?", C.MULTI_METRIC, D.MEDIUM,
    E(metrics=["capital_added", "capital_withdrawn"]))

add("Compare total sales and net sales this month.", C.MULTI_METRIC, D.MEDIUM,
    E(metrics=["total_sales", "net_sales"], time_range="this_month"))

add("Show total expenses and total payments last month.", C.MULTI_METRIC, D.MEDIUM,
    E(metrics=["total_expenses", "total_payments"], time_range="last_month"))

add("Compare cash in, cash out, and total expenses.", C.MULTI_METRIC, D.HARD,
    E(metrics=["cash_in", "cash_out", "total_expenses"]))

add("Show monthly total sales and total expenses.", C.MULTI_METRIC, D.HARD,
    E(metrics=["total_sales", "total_expenses"], time_grain="monthly"))

add("Compare capital added this year to capital withdrawn this year.", C.MULTI_METRIC, D.HARD,
    E(metrics=["capital_added", "capital_withdrawn"], time_range="this_year"))

add("Show orders and total payments today.", C.MULTI_METRIC, D.MEDIUM,
    E(metrics=["orders_count", "total_payments"], time_range="today"))


# --------------------------------------------------------------------------- #
# Category 7 -- Ambiguous or invalid queries (expected to fail correctly)
# --------------------------------------------------------------------------- #

add("How is the business doing?", C.AMBIGUOUS_INVALID, D.HARD,
    failed_stage=Stage.PARSER,
    failure_reason="No extractable metric, dimension, or time expression; too open-ended to parse.")

add("Show me everything.", C.AMBIGUOUS_INVALID, D.HARD,
    failed_stage=Stage.PARSER,
    failure_reason="No specific metric requested; cannot be mapped to a QueryRequest.")

add("What will our sales be next month?", C.AMBIGUOUS_INVALID, D.HARD,
    failed_stage=Stage.TIME_RESOLUTION,
    failure_reason="Requests a forecast/future value the system has no capability to produce.")

add("Give me profit by customer satisfaction.", C.AMBIGUOUS_INVALID, D.HARD,
    failed_stage=Stage.SEMANTIC_RESOLUTION,
    failure_reason="'profit' and 'customer satisfaction' are not registered metric/dimension.")

add("What's our best marketing channel?", C.AMBIGUOUS_INVALID, D.HARD,
    failed_stage=Stage.SEMANTIC_RESOLUTION,
    failure_reason="No marketing-channel dimension exists in the current registry.")

add("Why did expenses go up?", C.AMBIGUOUS_INVALID, D.HARD,
    failed_stage=Stage.PARSER,
    failure_reason="Causal/explanatory question; system only supports descriptive metric lookups.")

add("Should we cut costs next quarter?", C.AMBIGUOUS_INVALID, D.HARD,
    failed_stage=Stage.PARSER,
    failure_reason="Advisory/recommendation question, not a metric lookup.")

add("Show sales by employee performance rating.", C.AMBIGUOUS_INVALID, D.HARD,
    failed_stage=Stage.SEMANTIC_RESOLUTION,
    failure_reason="'employee performance rating' is not a registered dimension.")

add("asdkjaslkdj sales??", C.AMBIGUOUS_INVALID, D.HARD,
    failed_stage=Stage.PARSER,
    failure_reason="Malformed / low-signal input; parser should reject rather than guess.")

add("", C.AMBIGUOUS_INVALID, D.EASY,
    failed_stage=Stage.PARSER,
    failure_reason="Empty question; must be rejected before reaching the LLM parser.")


validate_dataset(cases)
save_dataset(cases, "/home/claude/evaluation/datasets/analytics_eval_v1.json", version="v1")
print(f"Wrote {len(cases)} cases.")

from collections import Counter
by_cat = Counter(c.category.value for c in cases)
by_status = Counter(c.expected_status.value for c in cases)
print("By category:", dict(by_cat))
print("By status:", dict(by_status))