"""
Phase 9.3.4 -- Filter Resolver.

Resolves one FilterCondition's dimension AND value to canonical form:

  - the dimension goes through the same resolution as
    dimension_resolver.resolve_dimension (alias -> canonical column,
    checked against the resolved metric's supported dimensions --
    "Metric x Filter compatibility").

  - if the canonical dimension names a business entity (customer,
    product, supplier, partner, location, cash account), the VALUE is
    additionally resolved to that entity's canonical ID via an
    injected EntityLookupFn -- e.g. "Mirpur" -> "LOC_001" -- and the
    filter's dimension switches to the corresponding *_id column,
    since the SQL layer should filter on stable IDs rather than
    display names.

  - for every other dimension (categorical, numeric, date), or when
    no EntityLookupFn is configured, the value is only lightly
    normalized (whitespace-trimmed), not looked up.

No fuzzy/typo-tolerant matching happens IN THIS MODULE. Any
substring/fuzzy matching is entirely the injected EntityLookupFn's
responsibility (in production, a DB ILIKE/full-text search against
the real customer/location/... tables) -- this module only decides
whether what came back is unambiguous. Same dependency-injection
pattern Phase 9.2 used for the LLM call: swap the implementation
without touching this resolver's logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional, Sequence

from etl.analytics.schemas import FilterCondition
from etl.analytics.semantic.dimension_resolver import resolve_dimension
from etl.analytics.semantic.models import ResolutionResult, ResolvedFilter
from etl.analytics.semantic.normalizer import normalize_text

# canonical "name" dimension -> the canonical "id" dimension the SQL
# layer should filter on once the name is resolved to a stable ID.
ENTITY_DIMENSIONS: dict[str, str] = {
    "customer_name": "customer_id",
    "product_name": "product_id",
    "supplier_name": "supplier_id",
    "partner_name": "partner_id",
    "location_name": "location_id",
    "cash_account_name": "cash_account_id",
    "from_location_name": "from_location_id",
    "to_location_name": "to_location_id",
}

# Operators whose value is a business entity name that might need ID
# resolution. Deliberately excludes:
#   - "like": a LIKE pattern is meant to run directly against the
#     *_name column, not collapse to a single ID.
#   - comparison operators (gt/gte/lt/lte) and "between": assumed
#     numeric/date, entity lookup doesn't apply.
#   - nullary operators (is_null/is_not_null): no value to resolve.
_ENTITY_RESOLVABLE_OPERATORS = frozenset({"eq", "ne", "in", "not_in"})
_LIST_OPERATORS = frozenset({"in", "not_in"})
_NULLARY_OPERATORS = frozenset({"is_null", "is_not_null"})


@dataclass(frozen=True)
class EntityMatch:
    """One candidate business entity returned by an EntityLookupFn."""

    id: str
    name: str


# (canonical "*_name" dimension, raw search text) -> candidate matches.
# e.g. entity_lookup("location_name", "Mirpur") -> matches from the
# location directory. Bring your own DB-backed implementation; see
# StaticEntityDirectory below for a testable in-memory stand-in.
EntityLookupFn = Callable[[str, str], Sequence[EntityMatch]]


class StaticEntityDirectory:
    """
    A simple in-memory EntityLookupFn, useful for tests and demos.

    Matching here is intentionally naive (bidirectional substring
    containment) to stand in for what a real `ILIKE '%value%'` query
    would return -- it is NOT what filter_resolver relies on for
    correctness; resolve_filter only trusts whatever candidates come
    back and decides if they're unambiguous. Production code should
    inject a real DB-backed lookup instead.
    """

    def __init__(self, entities: dict[str, Sequence[EntityMatch]]) -> None:
        self._entities = {k: tuple(v) for k, v in entities.items()}

    def __call__(self, dimension: str, query: str) -> tuple[EntityMatch, ...]:
        pool = self._entities.get(dimension, ())
        normalized_query = normalize_text(query)
        if not normalized_query:
            return ()
        return tuple(
            m
            for m in pool
            if normalized_query in normalize_text(m.name)
            or normalize_text(m.name) in normalized_query
        )


def _resolve_entity_value(
    *,
    name_dimension: str,
    raw_value: str,
    entity_lookup: EntityLookupFn,
    field_name: str,
) -> ResolutionResult:
    normalized_query = normalize_text(raw_value)
    matches = tuple(entity_lookup(name_dimension, raw_value))

    # An exact (normalized) name match wins outright, even if the
    # lookup also returned other loosely-matching candidates -- e.g.
    # the directory has both "Mirpur" and "Mirpur North" and the user
    # typed exactly "Mirpur".
    exact = [m for m in matches if normalize_text(m.name) == normalized_query]
    if len(exact) == 1:
        return ResolutionResult.resolved(field_name, raw_value, exact[0].id)
    if len(exact) > 1:
        return ResolutionResult.ambiguous(
            field_name,
            raw_value,
            tuple(sorted(m.id for m in exact)),
            message=f"Multiple {name_dimension} entries are named exactly {raw_value!r}.",
        )

    if len(matches) == 1:
        return ResolutionResult.resolved(field_name, raw_value, matches[0].id)
    if len(matches) == 0:
        return ResolutionResult.not_found(
            field_name, raw_value, message=f"No {name_dimension} entry matches {raw_value!r}."
        )
    return ResolutionResult.ambiguous(
        field_name,
        raw_value,
        tuple(sorted(m.name for m in matches)),
        message=f"{raw_value!r} matches multiple {name_dimension} entries.",
    )


def _normalize_value(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, tuple)):
        return [v.strip() if isinstance(v, str) else v for v in value]
    return value


def resolve_filter(
    raw_filter: FilterCondition,
    *,
    allowed_dimensions: frozenset[str],
    entity_lookup: Optional[EntityLookupFn] = None,
) -> tuple[ResolutionResult, Optional[ResolvedFilter]]:
    """
    Resolve one FilterCondition's dimension and value.

    Returns (ResolutionResult, ResolvedFilter | None): the
    ResolvedFilter is populated only when the ResolutionResult's
    status is RESOLVED, so callers can always check `.is_resolved`
    first without a None-check dance.
    """

    field_name = f"filter:{raw_filter.dimension}"

    dim_result = resolve_dimension(
        raw_filter.dimension, allowed_dimensions=allowed_dimensions, field_name=field_name
    )
    if not dim_result.is_resolved:
        return dim_result, None

    canonical_dimension: str = dim_result.resolved_value
    operator = raw_filter.operator
    raw_value = raw_filter.value

    if operator in _NULLARY_OPERATORS:
        return (
            ResolutionResult.resolved(field_name, raw_filter.dimension, canonical_dimension),
            ResolvedFilter(
                dimension=canonical_dimension,
                operator=operator,
                value=None,
                original_dimension=raw_filter.dimension,
                original_value=raw_value,
            ),
        )

    entity_id_dimension = ENTITY_DIMENSIONS.get(canonical_dimension)
    use_entity_resolution = (
        entity_id_dimension is not None
        and entity_lookup is not None
        and operator in _ENTITY_RESOLVABLE_OPERATORS
    )

    if not use_entity_resolution:
        # Not an entity dimension, no directory wired, or an
        # operator (like/between/comparison) entity lookup doesn't
        # apply to -- pass the value through with light normalization.
        return (
            ResolutionResult.resolved(field_name, raw_filter.dimension, canonical_dimension),
            ResolvedFilter(
                dimension=canonical_dimension,
                operator=operator,
                value=_normalize_value(raw_value),
                original_dimension=raw_filter.dimension,
                original_value=raw_value,
            ),
        )

    # The guard above guarantees that an entity lookup is configured here.
    assert entity_lookup is not None

    if operator in _LIST_OPERATORS:
        if not isinstance(raw_value, (list, tuple)) or len(raw_value) == 0:
            return (
                ResolutionResult.invalid(
                    field_name,
                    str(raw_value),
                    f"Operator '{operator}' requires a non-empty list value.",
                ),
                None,
            )
        resolved_ids = []
        for i, item in enumerate(raw_value):
            item_result = _resolve_entity_value(
                name_dimension=canonical_dimension,
                raw_value=str(item),
                entity_lookup=entity_lookup,
                field_name=f"{field_name}[{i}]",
            )
            if not item_result.is_resolved:
                return item_result, None
            resolved_ids.append(item_result.resolved_value)
        assert entity_id_dimension is not None
        return (
            ResolutionResult.resolved(field_name, raw_filter.dimension, entity_id_dimension),
            ResolvedFilter(
                dimension=entity_id_dimension,
                operator=operator,
                value=resolved_ids,
                original_dimension=raw_filter.dimension,
                original_value=raw_value,
            ),
        )

    value_result = _resolve_entity_value(
        name_dimension=canonical_dimension,
        raw_value=str(raw_value),
        entity_lookup=entity_lookup,
        field_name=field_name,
    )
    if not value_result.is_resolved:
        return value_result, None

    assert entity_id_dimension is not None
    return (
        ResolutionResult.resolved(field_name, raw_filter.dimension, entity_id_dimension),
        ResolvedFilter(
            dimension=entity_id_dimension,
            operator=operator,
            value=value_result.resolved_value,
            original_dimension=raw_filter.dimension,
            original_value=raw_value,
        ),
    )
