"""Pydantic schemas for the analytics API boundary."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AnalyticalQuestionRequest(BaseModel):
    question: str = Field(..., min_length=1)


class QueryContextSchema(BaseModel):
    metrics: list[str] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)
    filters: list[dict[str, Any]] = Field(default_factory=list)
    time_grain: str | None = None


class MetricMetadataSchema(BaseModel):
    metric: str
    label: str
    unit: str | None = None


class ResponseMetadataSchema(BaseModel):
    metrics: list[MetricMetadataSchema] = Field(default_factory=list)
    row_count: int = 0


class AnalyticalErrorSchema(BaseModel):
    code: str
    message: str
    stage: str | None = None


class AnalyticalResponseSchema(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    success: bool
    status: str
    query: QueryContextSchema | None = None
    metadata: ResponseMetadataSchema | None = None
    data: list[dict[str, Any]] = Field(default_factory=list)
    error: AnalyticalErrorSchema | None = None
