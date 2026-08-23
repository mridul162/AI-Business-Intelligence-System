"""Analytics API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from api.dependencies.analytics import (
    get_analytics_service,
    get_response_builder,
)
from api.schemas.analytics import AnalyticalQuestionRequest, AnalyticalResponseSchema
from etl.analytics.response.builder import AnalyticalResponseBuilder
from etl.analytics.service.analytical_query_service import AnalyticalQueryService

router = APIRouter(prefix="/analytics", tags=["analytics"])

_HTTP_STATUS_BY_STAGE = {
    "semantic_resolution": status.HTTP_422_UNPROCESSABLE_CONTENT,
    "query_building": status.HTTP_400_BAD_REQUEST,
    "query_validation": status.HTTP_400_BAD_REQUEST,
    "query_execution": status.HTTP_502_BAD_GATEWAY,
}


@router.post("/query", response_model=AnalyticalResponseSchema)
def query_analytics(
    request: AnalyticalQuestionRequest,
    service: AnalyticalQueryService = Depends(get_analytics_service),
    response_builder: AnalyticalResponseBuilder = Depends(get_response_builder),
) -> dict:
    service_result = service.query(request.question)
    response = response_builder.build(service_result)

    if response.success:
        return response.to_dict()

    error = response.error
    detail = {
        "code": error.code if error else "UNKNOWN_ERROR",
        "message": (
            "Unable to execute the analytical query."
            if error and error.stage == "query_execution"
            else error.message if error else "Unable to execute the analytical query."
        ),
        "stage": error.stage if error else service_result.error_stage,
    }
    raise HTTPException(
        status_code=_HTTP_STATUS_BY_STAGE.get(
            service_result.error_stage or "",
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ),
        detail=detail,
    )
