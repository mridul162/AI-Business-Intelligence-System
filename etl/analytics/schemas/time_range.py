"""
TimeRange schema (Phase 9.1).

A TimeRange is either:

  - resolved:   explicit `start`/`end` dates, ready to hand straight
                to the existing query layer (etl.analytics.query).
  - unresolved: a `preset` keyword (e.g. "current_month") or a
                free-text `label` (e.g. "August", "Eid week") that the
                NL parser recognized as time-related but couldn't
                confidently turn into dates itself.

Turning an unresolved TimeRange into a resolved one is Phase 9.4's
job (a deterministic time resolver, not the LLM). This module only
defines the shape and rejects structurally nonsensical input; it does
not do any date math.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

# Preset keywords the Phase 9.4 time resolver is expected to support.
# Kept here (rather than in the resolver) because it's part of the
# *contract* between the NL layer and the resolver: the NL layer must
# only ever emit one of these, never an arbitrary string.
KNOWN_PRESETS = frozenset(
    {
        "today",
        "yesterday",
        "current_week",
        "last_week",
        "current_month",
        "last_month",
        "current_quarter",
        "last_quarter",
        "current_year",
        "last_year",
        "last_7_days",
        "last_30_days",
        "last_90_days",
        "year_to_date",
        "month_to_date",
        "all_time",
    }
)


@dataclass(frozen=True)
class TimeRange:
    """
    A time range as understood by the NL layer.

    Exactly one "source" of meaning must be present:
      - `preset` (a known keyword), or
      - `label` (raw text the resolver will interpret), or
      - `start`/`end` (already resolved dates).

    `start`/`end` may additionally be set alongside a `preset`/`label`
    once resolution has happened, at which point `is_resolved` is
    True and the preset/label become informational only (useful for
    Phase 9.6's response generator, e.g. "you asked for 'last month',
    which I resolved to July 2026").
    """

    preset: str | None = None
    label: str | None = None
    start: date | None = None
    end: date | None = None

    def __post_init__(self) -> None:
        if self.preset is not None and self.label is not None:
            raise ValueError(
                "TimeRange cannot have both 'preset' and 'label' set — "
                "pick one way of describing the unresolved range."
            )
        if (
            self.preset is None
            and self.label is None
            and self.start is None
            and self.end is None
        ):
            raise ValueError(
                "TimeRange must specify at least one of: preset, label, "
                "start, or end."
            )
        if self.preset is not None and self.preset not in KNOWN_PRESETS:
            raise ValueError(
                f"Unknown time range preset {self.preset!r}. Must be one "
                f"of: {sorted(KNOWN_PRESETS)}"
            )
        if self.start is not None and self.end is not None and self.start > self.end:
            raise ValueError("TimeRange.start must not be after TimeRange.end.")

    @property
    def is_resolved(self) -> bool:
        """True once this range has explicit dates the query layer can
        use directly. A TimeRange can be resolved (start/end present)
        even if it also carries the original preset/label for display
        purposes.

        The 'all_time' preset is a special case: it's resolved as
        soon as it's constructed, since it deliberately carries NO
        dates (Phase 9.4's time resolver maps it to start=None,
        end=None, which the Phase 8 query layer already treats as
        "no date filter" -- see AnalyticalQueryRequest.to_query_request).
        Without this, 'all_time' -- despite being one of the presets
        the NL layer is allowed to emit -- would be permanently stuck
        NOT resolved, since it has no start/end to check for."""
        return self.start is not None or self.end is not None or self.preset == "all_time"

    @classmethod
    def for_preset(cls, preset: str) -> "TimeRange":
        """Construct an unresolved range from a known preset keyword."""
        return cls(preset=preset)

    @classmethod
    def for_label(cls, label: str) -> "TimeRange":
        """Construct an unresolved range from free text the parser
        couldn't confidently turn into a preset or dates itself."""
        return cls(label=label)

    @classmethod
    def for_dates(cls, start: date | None, end: date | None = None) -> "TimeRange":
        """Construct an already-resolved range from explicit dates."""
        return cls(start=start, end=end)