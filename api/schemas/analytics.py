"""Pydantic schemas for the analytics API boundary."""

from __future__ import annotations

from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


class AnalyticalQuestionRequest(BaseModel):
    """Incoming natural-language analytical question."""

    question: str = Field(
        ...,
        min_length=1,
        max_length=2000,
    )

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        """Reject whitespace-only questions."""
        value = value.strip()

        if not value:
            raise ValueError(
                "Analytical question must not be empty."
            )

        return value


class QueryContextSchema(BaseModel):
    """Resolved query context echoed to the API consumer."""

    metrics: list[str] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)
    filters: list[dict[str, Any]] = Field(default_factory=list)
    time_grain: str | None = None


class MetricMetadataSchema(BaseModel):
    """Metadata describing one requested metric."""

    metric: str
    label: str
    unit: str | None = None


class ResponseMetadataSchema(BaseModel):
    """Metadata about requested metrics and returned rows."""

    metrics: list[MetricMetadataSchema] = Field(default_factory=list)
    row_count: int = 0


class AnalyticalErrorSchema(BaseModel):
    """Public analytical error contract."""

    code: str
    message: str
    stage: str | None = None


class AnalyticalResponseSchema(BaseModel):
    """Stable HTTP response schema for analytical queries."""

    model_config = ConfigDict(use_enum_values=True)

    success: bool
    status: str
    query: QueryContextSchema | None = None
    metadata: ResponseMetadataSchema | None = None
    data: list[dict[str, Any]] = Field(default_factory=list)
    error: AnalyticalErrorSchema | None = None

class APIErrorResponseSchema(BaseModel):
    """Public HTTP error response for analytics API failures."""

    detail: AnalyticalErrorSchema