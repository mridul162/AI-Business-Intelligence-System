"""
Shared text normalization for the semantic resolution layer.
"""

from __future__ import annotations

import re

_WHITESPACE_RE = re.compile(r"\s+")


def normalize_text(value: str | None) -> str:
    """
    Case- and whitespace-insensitive normalization used throughout
    semantic resolution: lowercases, treats underscores as spaces,
    collapses internal whitespace, and trims.

        normalize_text(" Mirpur ")   == "mirpur"
        normalize_text("MIRPUR")     == "mirpur"
        normalize_text("product_category") == "product category"

    This is deliberately NOT fuzzy or typo-tolerant matching (no
    edit distance, no phonetic matching, no transliteration). Per the
    Phase 9.3 design notes: multilingual/fuzzy resolution is
    explicitly out of scope for this phase. Any substring/fuzzy
    matching that does happen (see filter_resolver.EntityLookupFn) is
    the injected lookup's responsibility, not this function's.
    """
    if not value:
        return ""
    text = value.replace("_", " ")
    text = _WHITESPACE_RE.sub(" ", text)
    return text.strip().lower()
