"""
Phase 9.4 -- Time Resolver.

Turns an *unresolved* TimeRange (a preset keyword like "last_month",
or a free-text label like "Eid week") into a *resolved* one (explicit
`start`/`end` dates the Phase 8 query layer can use directly), per
the contract etl.analytics.schemas.time_range.TimeRange already
documents:

    "Turning an unresolved TimeRange into a resolved one is Phase
    9.4's job (a deterministic time resolver, not the LLM)."

This module is deliberately narrow, matching that contract:

  - Every preset in TimeRange.KNOWN_PRESETS is computed here with
    plain date arithmetic against a `today` anchor (injectable, like
    filter_resolver's EntityLookupFn, so tests don't depend on the
    real clock) -- never an LLM call, never a database query.

  - A free-text `label` (e.g. "August", "Eid week") is NOT resolved
    here. The roadmap only asks this resolver to be deterministic;
    confidently turning arbitrary text into dates needs a smarter
    parser (or the LLM) upstream, so this returns NOT_FOUND with a
    message saying exactly that, rather than guessing.

Does not generate SQL and does not touch the metric registry -- same
"one job per phase" discipline as metric_resolver.py /
dimension_resolver.py / filter_resolver.py. Its only output is a
resolved TimeRange (via ResolutionResult), or a resolved copy of an
AnalyticalQueryRequest (via resolve_analytical_query_time), ready to
continue on to AnalyticalQueryRequest.to_query_request() and Phase
8's build_query().
"""

from __future__ import annotations

import calendar
import dataclasses
from datetime import date, timedelta
from typing import Optional

from etl.analytics.schemas.analytical_query import AnalyticalQueryRequest
from etl.analytics.schemas.time_range import KNOWN_PRESETS, TimeRange
from etl.analytics.semantic.models import ResolutionResult, SemanticResolutionError

_PresetBounds = tuple[Optional[date], Optional[date]]


def _week_start(day: date) -> date:
    """Monday of the ISO week containing `day`."""
    return day - timedelta(days=day.weekday())


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def _add_months(year: int, month: int, delta: int) -> tuple[int, int]:
    """Shift (year, month) by `delta` months, handling year rollover."""
    index = year * 12 + (month - 1) + delta
    return index // 12, index % 12 + 1


def _quarter_of(month: int) -> int:
    return (month - 1) // 3 + 1


def _quarter_bounds(year: int, quarter: int) -> tuple[date, date]:
    start_month = (quarter - 1) * 3 + 1
    end_month = start_month + 2
    _, last_day = calendar.monthrange(year, end_month)
    return date(year, start_month, 1), date(year, end_month, last_day)


def _resolve_preset_bounds(preset: str, today: date) -> _PresetBounds:
    """Pure date arithmetic for one KNOWN_PRESETS value. Every branch
    here corresponds 1:1 to an entry in TimeRange.KNOWN_PRESETS --
    _MISSING_PRESET_BRANCH below guards against the two ever drifting
    apart silently."""

    if preset == "today":
        return today, today

    if preset == "yesterday":
        y = today - timedelta(days=1)
        return y, y

    if preset == "current_week":
        start = _week_start(today)
        return start, start + timedelta(days=6)

    if preset == "last_week":
        start = _week_start(today) - timedelta(days=7)
        return start, start + timedelta(days=6)

    if preset == "current_month":
        return _month_bounds(today.year, today.month)

    if preset == "last_month":
        y, m = _add_months(today.year, today.month, -1)
        return _month_bounds(y, m)

    if preset == "current_quarter":
        return _quarter_bounds(today.year, _quarter_of(today.month))

    if preset == "last_quarter":
        quarter = _quarter_of(today.month)
        year, quarter = (
            (today.year, quarter - 1) if quarter > 1 else (today.year - 1, 4)
        )
        return _quarter_bounds(year, quarter)

    if preset == "current_year":
        return date(today.year, 1, 1), date(today.year, 12, 31)

    if preset == "last_year":
        return date(today.year - 1, 1, 1), date(today.year - 1, 12, 31)

    if preset == "last_7_days":
        return today - timedelta(days=6), today

    if preset == "last_30_days":
        return today - timedelta(days=29), today

    if preset == "last_90_days":
        return today - timedelta(days=89), today

    if preset == "year_to_date":
        return date(today.year, 1, 1), today

    if preset == "month_to_date":
        return date(today.year, today.month, 1), today

    if preset == "all_time":
        # No bound at all, by design -- see TimeRange.is_resolved's
        # special case for this preset.
        return None, None

    raise AssertionError(  # pragma: no cover
        f"KNOWN_PRESETS contains {preset!r} but time_resolver.py has no "
        "matching branch. Add one to _resolve_preset_bounds."
    )


# Fail loudly (at import time, in CI) if TimeRange.KNOWN_PRESETS ever
# grows a preset this module doesn't know how to compute, rather than
# discovering it as a runtime AssertionError from a real request.
_missing = KNOWN_PRESETS - {
    "today", "yesterday", "current_week", "last_week", "current_month",
    "last_month", "current_quarter", "last_quarter", "current_year",
    "last_year", "last_7_days", "last_30_days", "last_90_days",
    "year_to_date", "month_to_date", "all_time",
}
if _missing:  # pragma: no cover
    raise AssertionError(
        f"TimeRange.KNOWN_PRESETS has preset(s) {sorted(_missing)} that "
        "time_resolver.py doesn't implement yet."
    )


def resolve_time_range(
    time_range: Optional[TimeRange],
    *,
    today: Optional[date] = None,
    field_name: str = "time_range",
) -> ResolutionResult:
    """
    Resolve one TimeRange to explicit dates.

    - `time_range is None`: nothing was asked for -- resolved as "no
      date filter", same as Phase 8 already treats a QueryRequest
      with date_from=date_to=None.
    - Already resolved (`time_range.is_resolved`): passed through
      unchanged -- this resolver never overwrites dates the NL layer
      (or an earlier resolution pass) already supplied.
    - A known `preset`: computed deterministically against `today`
      (defaults to `date.today()` -- pass an explicit date in tests
      so they don't depend on the real clock, the same
      dependency-injection pattern filter_resolver.EntityLookupFn
      uses for entity lookups).
    - A `label`: NOT_FOUND. See module docstring -- free text needs a
      smarter parser than this deterministic resolver provides.
    """

    if time_range is None:
        return ResolutionResult.resolved(field_name, "", None)

    if time_range.is_resolved:
        return ResolutionResult.resolved(
            field_name, time_range.preset or time_range.label or "", time_range
        )

    if time_range.label is not None:
        return ResolutionResult.not_found(
            field_name,
            time_range.label,
            message=(
                f"Time range label {time_range.label!r} can't be resolved "
                "deterministically. Phase 9.4's time resolver only "
                f"understands known presets ({sorted(KNOWN_PRESETS)}); "
                "free-text labels need a smarter date parser upstream "
                "before reaching this resolver."
            ),
        )

    # __post_init__ guarantees at least one of preset/label/start/end
    # is set; is_resolved being False rules out start/end; label is
    # None (checked above) -- so preset must be set.
    preset = time_range.preset
    assert preset is not None  # for type-checkers; guaranteed by the above

    anchor = today if today is not None else date.today()
    start, end = _resolve_preset_bounds(preset, anchor)

    resolved = TimeRange(preset=preset, start=start, end=end)
    return ResolutionResult.resolved(field_name, preset, resolved)


def resolve_analytical_query_time(
    request: AnalyticalQueryRequest,
    *,
    today: Optional[date] = None,
) -> AnalyticalQueryRequest:
    """
    Return a copy of `request` with `time_range` fully resolved.

    Meant to run right after Phase 9.3's SemanticResolver and before
    AnalyticalQueryRequest.to_query_request() / Phase 8's
    build_query():

        resolved = SemanticResolver().resolve(raw_request)          # Phase 9.3
        bridged = resolved.to_analytical_query_request()
        time_resolved = resolve_analytical_query_time(bridged)      # Phase 9.4
        compiled = build_query(time_resolved.to_query_request())    # Phase 8

    Raises:
        SemanticResolutionError: If `request.time_range` is set but
            couldn't be resolved (currently: a free-text label).
            Carries the single failing ResolutionResult in `.issues`,
            same shape SemanticResolutionError already uses for
            metric/dimension/filter failures, so callers can handle
            every phase's resolution errors uniformly.
    """
    result = resolve_time_range(request.time_range, today=today, field_name="time_range")
    if not result.is_resolved:
        raise SemanticResolutionError((result,))

    if result.resolved_value is request.time_range:
        return request

    return dataclasses.replace(request, time_range=result.resolved_value)
