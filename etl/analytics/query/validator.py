"""
Query validation.

This is the security and correctness boundary between the LLM/agent
layer and the SQL builder. Every field on a QueryRequest is checked
here before builder.py is allowed to turn it into SQL:

  - metric names must exist in the metric registry
  - all requested metrics must share one source_view (no cross-view
    joins in this phase)
  - dimensions must be identifiers matching an allowlist derived from
    the requested metrics' `supported_dimensions`
  - time_grain, if given, must be supported by every requested metric
  - filters must reference allowed dimensions and carry a value shape
    that matches their operator
  - order_by fields must resolve to a selected dimension, the time
    bucket, or a requested metric's output_field
  - limit must be a positive integer

Nothing here builds SQL strings. It only proves the request is safe
and well-formed, and hands the builder a ValidatedQuery it can trust.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from etl.analytics.metrics.definitions import MetricDefinition, TimeGrain
from etl.analytics.metrics.registry import get_metric
from etl.analytics.query.models import (
    LIST_OPERATORS,
    NULLARY_OPERATORS,
    FilterOperator,
    OrderBy,
    QueryFilter,
    QueryRequest,
)
from etl.analytics.query.time_grains import PERIOD_ALIAS

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class ValidationError(Exception):
    """Raised when a QueryRequest is unsafe or malformed."""


def _is_safe_identifier(name: str) -> bool:
    return bool(_IDENTIFIER_RE.match(name))


@dataclass(frozen=True)
class ValidatedQuery:
    """A QueryRequest that has passed validation, plus the derived
    facts the builder needs (resolved metrics, shared source view,
    and the set of dimension names it's safe to project/group by)."""

    request: QueryRequest
    metrics: tuple[MetricDefinition, ...]
    source_view: str
    allowed_dimensions: frozenset[str]


def _resolve_metrics(metric_names: tuple[str, ...]) -> tuple[MetricDefinition, ...]:
    if not metric_names:
        raise ValidationError("A query must request at least one metric.")

    resolved: list[MetricDefinition] = []
    for name in metric_names:
        try:
            resolved.append(get_metric(name))
        except KeyError as exc:
            raise ValidationError(str(exc)) from exc

    return tuple(resolved)


def _validate_shared_source_view(metrics: tuple[MetricDefinition, ...]) -> str:
    views = {m.source_view for m in metrics}
    if len(views) > 1:
        raise ValidationError(
            "All metrics in one query must share the same source_view. "
            f"Got: {sorted(views)}. Split this into separate queries, "
            "one per view."
        )
    return next(iter(views))


def _allowed_dimensions(metrics: tuple[MetricDefinition, ...]) -> frozenset[str]:
    dims: set[str] = set()
    for m in metrics:
        dims.update(m.supported_dimensions)
    return frozenset(dims)


def _validate_dimensions(
    dimensions: tuple[str, ...], allowed: frozenset[str]
) -> None:
    for dim in dimensions:
        if not _is_safe_identifier(dim):
            raise ValidationError(f"Dimension '{dim}' is not a valid identifier.")
        if dim not in allowed:
            raise ValidationError(
                f"Dimension '{dim}' is not supported by the requested "
                f"metrics. Allowed dimensions: {sorted(allowed)}"
            )


def _validate_time_grain(
    time_grain: TimeGrain | None, metrics: tuple[MetricDefinition, ...]
) -> None:
    if time_grain is None:
        return

    supported = set(metrics[0].supported_time_grains)
    for m in metrics[1:]:
        supported &= set(m.supported_time_grains)

    if time_grain not in supported:
        raise ValidationError(
            f"Time grain '{time_grain}' is not supported by all requested "
            f"metrics. Common supported grains: {sorted(supported)}"
        )


def _validate_filter(filt: QueryFilter, allowed: frozenset[str]) -> None:
    if not _is_safe_identifier(filt.dimension):
        raise ValidationError(
            f"Filter dimension '{filt.dimension}' is not a valid identifier."
        )
    if filt.dimension not in allowed:
        raise ValidationError(
            f"Filter dimension '{filt.dimension}' is not supported by the "
            f"requested metrics. Allowed dimensions: {sorted(allowed)}"
        )

    if filt.operator in NULLARY_OPERATORS:
        if filt.value is not None:
            raise ValidationError(
                f"Operator '{filt.operator.value}' does not take a value "
                f"(dimension '{filt.dimension}')."
            )
        return

    if filt.operator in LIST_OPERATORS:
        if not isinstance(filt.value, (list, tuple)) or len(filt.value) == 0:
            raise ValidationError(
                f"Operator '{filt.operator.value}' requires a non-empty "
                f"list value (dimension '{filt.dimension}')."
            )
        return

    if filt.operator is FilterOperator.BETWEEN:
        if (
            not isinstance(filt.value, (list, tuple))
            or len(filt.value) != 2
        ):
            raise ValidationError(
                "Operator 'between' requires a two-item (low, high) value "
                f"(dimension '{filt.dimension}')."
            )
        return

    # eq / ne / gt / gte / lt / lte / like all require a scalar value.
    if filt.value is None:
        raise ValidationError(
            f"Operator '{filt.operator.value}' requires a value "
            f"(dimension '{filt.dimension}')."
        )


def _validate_date_range(request: QueryRequest) -> None:
    if (
        request.date_from is not None
        and request.date_to is not None
        and request.date_from > request.date_to
    ):
        raise ValidationError("date_from must not be after date_to.")


def _validate_order_by(
    order_by: tuple[OrderBy, ...],
    allowed: frozenset[str],
    time_grain: TimeGrain | None,
    output_fields: frozenset[str],
) -> None:
    valid_fields = set(allowed) | output_fields
    if time_grain is not None:
        valid_fields.add(PERIOD_ALIAS)

    for entry in order_by:
        if entry.direction not in ("asc", "desc"):
            raise ValidationError(
                f"order_by direction must be 'asc' or 'desc', got "
                f"'{entry.direction}'."
            )
        if entry.field not in valid_fields:
            raise ValidationError(
                f"order_by field '{entry.field}' must be a requested "
                f"dimension, the time bucket ('{PERIOD_ALIAS}'), or a "
                f"requested metric's output_field. Valid fields: "
                f"{sorted(valid_fields)}"
            )


def _validate_limit(limit: int | None) -> None:
    if limit is not None and (not isinstance(limit, int) or limit <= 0):
        raise ValidationError("limit must be a positive integer.")


def validate_query(request: QueryRequest) -> ValidatedQuery:
    """Validate a QueryRequest and return the resolved metrics and
    derived metadata the builder needs.

    Raises:
        ValidationError: If the request is unsafe or malformed.
    """

    metrics = _resolve_metrics(request.metrics)
    source_view = _validate_shared_source_view(metrics)
    allowed_dims = _allowed_dimensions(metrics)

    _validate_dimensions(request.dimensions, allowed_dims)
    _validate_time_grain(request.time_grain, metrics)

    for filt in request.filters:
        _validate_filter(filt, allowed_dims)

    _validate_date_range(request)

    output_fields = frozenset(m.output_field for m in metrics)
    _validate_order_by(
        request.order_by, allowed_dims, request.time_grain, output_fields
    )
    _validate_limit(request.limit)

    return ValidatedQuery(
        request=request,
        metrics=metrics,
        source_view=source_view,
        allowed_dimensions=allowed_dims,
    )