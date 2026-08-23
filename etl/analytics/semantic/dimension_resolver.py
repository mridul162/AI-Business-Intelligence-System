"""
Phase 9.3.3 -- Dimension Resolver.

Resolves a raw dimension term -- already a canonical column name, or
a business-language alias like "customer" / "buyer" / "client" -- to
the canonical column name used by the metric registry, and checks it
against the set of dimensions the resolved metric(s) actually support
(the "Metric x Dimension compatibility" check from the roadmap).

DIMENSION_ALIASES is a small, hand-maintained table. Unlike metrics,
dimensions aren't first-class registry entries with their own
aliases field -- they're attributes of the underlying analytics
views, shared across several metrics (e.g. "customer_name" appears on
v_orders, v_sales, v_payments, ...), so there's no single natural
place to attach a dimension's aliases the way MetricDefinition.aliases
does for metrics.
"""

from __future__ import annotations

from etl.analytics.metrics.registry import list_metrics
from etl.analytics.semantic.models import ResolutionResult
from etl.analytics.semantic.normalizer import normalize_text

# business term -> canonical column name.
DIMENSION_ALIASES: dict[str, str] = {
    "customer": "customer_name",
    "buyer": "customer_name",
    "client": "customer_name",
    "product": "product_name",
    "item": "product_name",
    "goods": "product_name",
    "sku": "product_name",
    "category": "product_category",
    "location": "location_name",
    "branch": "location_name",
    "outlet": "location_name",
    "store": "location_name",
    "supplier": "supplier_name",
    "vendor": "supplier_name",
    "partner": "partner_name",
    "cash account": "cash_account_name",
    "account": "cash_account_name",
    "collector": "collected_by",
    "payer": "paid_by",
    "returned by": "returned_by",
    "from location": "from_location_name",
    "to location": "to_location_name",
    "destination": "to_location_name",
    "source location": "from_location_name",
}


def _all_known_dimensions() -> frozenset[str]:
    """Every dimension name supported by ANY registered metric --
    used to recognize an already-canonical column name (possibly in
    different casing/spacing) even before checking aliases."""
    dims: set[str] = set()
    for metric in list_metrics():
        dims.update(metric.supported_dimensions)
    return frozenset(dims)


def resolve_dimension(
    raw_value: str, *, allowed_dimensions: frozenset[str], field_name: str = "dimension"
) -> ResolutionResult:
    """
    Resolve one dimension term against `allowed_dimensions` -- the
    set of dimensions the metric(s) actually requested support (see
    semantic_resolver._allowed_dimensions). A dimension that's
    canonical/known but NOT in `allowed_dimensions` is a compatibility
    failure (status INVALID), distinct from a dimension nobody
    recognizes at all (status NOT_FOUND).
    """

    if not raw_value or not raw_value.strip():
        return ResolutionResult.invalid(
            field_name, raw_value or "", "dimension value must not be empty."
        )

    # 1. Already an exact, canonical, supported column name.
    if raw_value in allowed_dimensions:
        return ResolutionResult.resolved(field_name, raw_value, raw_value)

    normalized = normalize_text(raw_value)
    known = _all_known_dimensions()

    # 2. Canonical column name modulo casing/spacing (e.g. "Product Category").
    for candidate in known:
        if normalize_text(candidate) == normalized:
            if candidate in allowed_dimensions:
                return ResolutionResult.resolved(field_name, raw_value, candidate)
            return ResolutionResult.invalid(
                field_name,
                raw_value,
                f"'{raw_value}' is a known dimension ('{candidate}') but isn't supported "
                f"here. Supported dimensions: {sorted(allowed_dimensions)}",
            )

    # 3. Business-language alias.
    canonical = DIMENSION_ALIASES.get(normalized)
    if canonical is not None:
        if canonical in allowed_dimensions:
            return ResolutionResult.resolved(field_name, raw_value, canonical)
        return ResolutionResult.invalid(
            field_name,
            raw_value,
            f"'{raw_value}' maps to dimension '{canonical}', which isn't supported here. "
            f"Supported dimensions: {sorted(allowed_dimensions)}",
        )

    return ResolutionResult.not_found(field_name, raw_value)
