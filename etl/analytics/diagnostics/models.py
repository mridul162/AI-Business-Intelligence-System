from dataclasses import dataclass


@dataclass(frozen=True)
class QueryPlanDiagnostic:
    plan_text: str
    execution_time_ms: float | None = None
    planning_time_ms: float | None = None