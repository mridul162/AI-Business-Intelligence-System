"""
Errors raised by the orchestrator's OWN coordination logic.

These are deliberately narrow. Planner/builder/executor/merger
failures are NOT caught or translated here -- they propagate as-is
so they can be logged/classified upstream with their original type
intact (see analytics_orchestrator.py's module docstring). Everything
in this file guards the orchestrator's boundary itself, not the
components it calls.
"""

from __future__ import annotations


class OrchestrationError(Exception):
    """Base class for all orchestrator-level errors."""


class OrchestratorConfigurationError(OrchestrationError):
    """Raised when the orchestrator is constructed without one of its
    required dependencies (planner, builder, executor, merger)."""


class InvalidPlanResultError(OrchestrationError):
    """
    Raised when the planner returns something that is neither a
    QueryPlan nor a MultiQueryPlan. This is a defensive check on the
    orchestrator's own control flow, not a re-wrap of a planning
    error -- a well-behaved planner should never trigger it.
    """