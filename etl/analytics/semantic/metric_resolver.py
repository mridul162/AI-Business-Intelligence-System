"""
Phase 9.3.2 -- Metric Resolver.

Resolves raw user language (an exact registry name, a display name,
or a declared alias) to a canonical metric name in
etl.analytics.metrics.registry.METRIC_REGISTRY.

Uses ONLY that registry's own `name` / `display_name` / `aliases`
fields -- no separate metric vocabulary is maintained here, per the
Phase 9.3 design rule of reusing the existing metric registry as the
single source of truth.

Deliberately does NOT do fuzzy/substring matching: which metric gets
queried controls which SQL runs, so only an exact (case- and
whitespace-insensitive) match against a name, display name, or
declared alias counts. A term matching more than one metric's alias
is genuine ambiguity and is surfaced as such, never silently resolved
to "the first match" or "the most popular one".
"""

from __future__ import annotations

from etl.analytics.metrics.registry import METRIC_REGISTRY
from etl.analytics.semantic.models import ResolutionResult
from etl.analytics.semantic.normalizer import normalize_text


def resolve_metric(raw_value: str, *, field_name: str = "metric") -> ResolutionResult:
    """Resolve one metric name/alias to a canonical METRIC_REGISTRY key."""

    if not raw_value or not raw_value.strip():
        return ResolutionResult.invalid(
            field_name, raw_value or "", "metric value must not be empty."
        )

    normalized = normalize_text(raw_value)

    # 1. Exact match against the canonical registry key.
    for name in METRIC_REGISTRY:
        if normalize_text(name) == normalized:
            return ResolutionResult.resolved(field_name, raw_value, name)

    # 2. Exact match against a metric's human-readable display name.
    for name, metric in METRIC_REGISTRY.items():
        if normalize_text(metric.display_name) == normalized:
            return ResolutionResult.resolved(field_name, raw_value, name)

    # 3. Exact match against a declared alias. Collected across ALL
    #    metrics rather than stopping at the first hit, so a term two
    #    metrics both claim is caught as ambiguous.
    candidates = sorted(
        name
        for name, metric in METRIC_REGISTRY.items()
        if normalized in {normalize_text(alias) for alias in metric.aliases}
    )
    if len(candidates) == 1:
        return ResolutionResult.resolved(field_name, raw_value, candidates[0])
    if len(candidates) > 1:
        return ResolutionResult.ambiguous(
            field_name,
            raw_value,
            tuple(candidates),
            message=(
                f"'{raw_value}' could mean any of: {', '.join(candidates)}. "
                "Ask the user which one they mean rather than guessing."
            ),
        )

    return ResolutionResult.not_found(field_name, raw_value)
