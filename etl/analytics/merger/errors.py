"""
Exceptions raised while merging ExecutedQuery results into a
MergedResult.

Kept deliberately small (five subclasses) rather than one-per-check,
per the Milestone 4 design review.
"""

from __future__ import annotations


class ResultMergeError(Exception):
    """Base class for all result-merger errors."""


class InvalidMergeInputError(ResultMergeError):
    """
    The call to merge() itself is malformed -- wrong number of
    executed queries, or two queries whose metric output fields
    collide (which would silently overwrite one metric's values with
    another's in the merged row).
    """


class ResultPlanMismatchError(ResultMergeError):
    """
    An executed query's plan doesn't correspond to exactly one plan
    in the MultiQueryPlan being merged.
    """


class MissingResultColumnError(ResultMergeError):
    """
    A query's ExecutionResult is missing a column its own BuiltQuery
    said it would produce (a metric output field, a dimension field,
    or the time bucket alias).
    """


class IncompatibleGroupingError(ResultMergeError):
    """
    The executed queries don't share the same grouping structure
    (same dimension fields, same order, same time-bucket presence),
    so their rows cannot be aligned by key.
    """


class DuplicateMergeKeyError(ResultMergeError):
    """
    One query produced more than one row for the same grouping key.
    The merger will not silently aggregate these -- duplicate keys
    signal an upstream planning/SQL bug, not something to paper over.
    """