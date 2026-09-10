"""
Combines the independently executed results of a MultiQueryPlan's
QueryPlans into one MergedResult.

This module aligns rows by a deterministic grouping key and unions
metric columns across queries. It does NOT:
  - resolve metric names or dimensions
  - generate or execute SQL
  - infer business definitions
  - compute derived metrics (e.g. net_cash = cash_in - cash_out)
  - call an LLM or format a natural-language answer
  - reinterpret MergeStrategy -- it only records which strategy the
    planner already chose

Row alignment, not calculation, is the entire job.
"""

from __future__ import annotations

from typing import Any

from etl.analytics.planner.query_plan import MultiQueryPlan
from etl.analytics.sql.sql_models import BuiltQuery

from .errors import (
    DuplicateMergeKeyError,
    IncompatibleGroupingError,
    InvalidMergeInputError,
    MissingResultColumnError,
    ResultPlanMismatchError,
)
from .merge_models import ExecutedQuery, MergedResult

# Value used for a metric when a query legitimately returned NO ROW
# at all for a given grouping key. Distinct from a row that exists
# but whose value is NULL -- that stays None. See _merge_row.
MISSING_METRIC_VALUE = 0

RowKey = tuple[Any, ...]


class ResultMerger:
    """Merges the ExecutedQuery results of one MultiQueryPlan."""

    def merge(
        self,
        multi_plan: MultiQueryPlan,
        executed_queries: tuple[ExecutedQuery, ...],
    ) -> MergedResult:
        """
        Args:
            multi_plan: the MultiQueryPlan whose plans were executed.
            executed_queries: one ExecutedQuery per plan in
                multi_plan.plans, in any order.

        Returns:
            A MergedResult with one row per grouping key that
            appeared in any of the executed queries.

        Raises:
            InvalidMergeInputError: wrong number of executed queries,
                or two queries produce colliding metric column names.
            ResultPlanMismatchError: an executed query's plan isn't
                exactly one of multi_plan.plans.
            MissingResultColumnError: a result is missing a column
                its own BuiltQuery said it would have.
            IncompatibleGroupingError: the queries don't share the
                same dimensions/time-bucket structure.
            DuplicateMergeKeyError: one query produced more than one
                row for the same grouping key.
        """
        ordered = _match_executed_queries_to_plans(multi_plan, executed_queries)
        _validate_result_columns(ordered)
        _validate_metric_field_uniqueness(ordered)
        grouping_fields = _validate_compatible_grouping(ordered)

        per_query_maps = [_index_rows_by_key(eq, grouping_fields) for eq in ordered]
        metric_fields_per_query = [eq.built_query.metric_output_fields for eq in ordered]

        ordered_keys = _union_keys_in_first_seen_order(per_query_maps)

        rows = tuple(
            _merge_row(key, grouping_fields, per_query_maps, metric_fields_per_query)
            for key in ordered_keys
        )

        columns = grouping_fields + tuple(
            field for fields in metric_fields_per_query for field in fields
        )

        return MergedResult(
            columns=columns,
            rows=rows,
            row_count=len(rows),
            merge_strategy=multi_plan.merge_strategy,
        )


# --------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------


def _match_executed_queries_to_plans(
    multi_plan: MultiQueryPlan,
    executed_queries: tuple[ExecutedQuery, ...],
) -> list[ExecutedQuery]:
    if len(executed_queries) != len(multi_plan.plans):
        raise InvalidMergeInputError(
            f"Expected {len(multi_plan.plans)} executed queries (one "
            f"per plan in the MultiQueryPlan), got {len(executed_queries)}."
        )

    remaining = list(executed_queries)
    ordered: list[ExecutedQuery] = []
    for plan in multi_plan.plans:
        matches = [eq for eq in remaining if eq.built_query.plan == plan]
        if not matches:
            raise ResultPlanMismatchError(
                f"No executed query corresponds to the plan for "
                f"source_view {plan.source_view!r}, metrics {plan.metrics!r}."
            )
        if len(matches) > 1:
            raise ResultPlanMismatchError(
                f"More than one executed query corresponds to the "
                f"plan for source_view {plan.source_view!r}, metrics "
                f"{plan.metrics!r}; each plan must have exactly one."
            )
        match = matches[0]
        ordered.append(match)
        remaining.remove(match)
    return ordered


def _validate_result_columns(executed_queries: list[ExecutedQuery]) -> None:
    for eq in executed_queries:
        available = set(eq.result.columns)
        required = set(eq.built_query.metric_output_fields) | set(
            eq.built_query.dimension_fields
        )
        if eq.built_query.time_bucket_alias is not None:
            required.add(eq.built_query.time_bucket_alias)

        missing = required - available
        if missing:
            raise MissingResultColumnError(
                f"Result for source_view {eq.built_query.plan.source_view!r} "
                f"is missing expected column(s): {sorted(missing)!r}."
            )


def _validate_metric_field_uniqueness(executed_queries: list[ExecutedQuery]) -> None:
    owner_by_field: dict[str, str] = {}
    for eq in executed_queries:
        for field in eq.built_query.metric_output_fields:
            if field in owner_by_field:
                raise InvalidMergeInputError(
                    f"Metric output field {field!r} is produced by more "
                    f"than one query in this merge (source_views "
                    f"{owner_by_field[field]!r} and "
                    f"{eq.built_query.plan.source_view!r}); merged "
                    f"columns must be unique."
                )
            owner_by_field[field] = eq.built_query.plan.source_view


def _validate_compatible_grouping(executed_queries: list[ExecutedQuery]) -> tuple[str, ...]:
    signatures = {_grouping_fields(eq.built_query) for eq in executed_queries}
    if len(signatures) > 1:
        raise IncompatibleGroupingError(
            "All queries in a merge must share the same grouping "
            "structure (same dimensions, same order, same time-bucket "
            f"presence); got differing structures: {sorted(signatures)!r}."
        )
    return next(iter(signatures))


def _grouping_fields(built_query: BuiltQuery) -> tuple[str, ...]:
    fields = tuple(built_query.dimension_fields)
    if built_query.time_bucket_alias is not None:
        fields += (built_query.time_bucket_alias,)
    return fields


# --------------------------------------------------------------------
# Row alignment
# --------------------------------------------------------------------


def _index_rows_by_key(
    executed_query: ExecutedQuery, grouping_fields: tuple[str, ...]
) -> dict[RowKey, dict[str, Any]]:
    """
    One query's rows, keyed by grouping-field values -- never by row
    position (see module docstring: alignment is by key, not zip()).
    """
    indexed: dict[RowKey, dict[str, Any]] = {}
    for row in executed_query.result.rows:
        key: RowKey = tuple(row[field] for field in grouping_fields)
        if key in indexed:
            raise DuplicateMergeKeyError(
                f"Query for source_view "
                f"{executed_query.built_query.plan.source_view!r} "
                f"produced more than one row for grouping key {key!r}."
            )
        indexed[key] = row
    return indexed


def _union_keys_in_first_seen_order(
    per_query_maps: list[dict[RowKey, dict[str, Any]]]
) -> list[RowKey]:
    """
    Deterministic union of every key seen across all queries, in
    first-seen order (query order, then row order within each query).
    Not sorted -- grouping values aren't guaranteed orderable across
    arbitrary types, and callers who need a specific row order should
    have the upstream SQL apply ORDER BY.
    """
    seen: set[RowKey] = set()
    ordered_keys: list[RowKey] = []
    for row_map in per_query_maps:
        for key in row_map:
            if key not in seen:
                seen.add(key)
                ordered_keys.append(key)
    return ordered_keys


def _merge_row(
    key: RowKey,
    grouping_fields: tuple[str, ...],
    per_query_maps: list[dict[RowKey, dict[str, Any]]],
    metric_fields_per_query: list[tuple[str, ...]],
) -> dict[str, Any]:
    merged: dict[str, Any] = dict(zip(grouping_fields, key))

    for row_map, metric_fields in zip(per_query_maps, metric_fields_per_query):
        row = row_map.get(key)
        for field in metric_fields:
            merged[field] = row[field] if row is not None else MISSING_METRIC_VALUE

    return merged