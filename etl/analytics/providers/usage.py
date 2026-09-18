from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class LLMUsageRecord:
    """Provider-reported usage for one successful completion attempt."""

    request_id: UUID | None
    model: str
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    latency_seconds: float
    attempt: int


class UsageRecorder(Protocol):
    def record(self, usage: LLMUsageRecord) -> None: ...