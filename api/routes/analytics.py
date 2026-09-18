"""Analytics API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from api.dependencies.analytics import get_analytics_application
from api.schemas.analytics import (
    AnalyticalQuestionRequest,
    AnalyticalResponseSchema,
)
from etl.analytics.application.analytics_application import AnalyticsApplication
from etl.analytics.executor.errors import (
    DatabaseConnectionError,
    QueryExecutionFailedError,
)
from etl.analytics.nl_query.exceptions import (
    InvalidQuestionError,
    LLMCallError,
    LLMResponseFormatError,
    LLMResponseValidationError,
)
from etl.analytics.semantic.models import SemanticResolutionError
from etl.analytics.planner.planner_errors import QueryPlanningLimitError
from etl.analytics.sql.errors import SQLBuilderError

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _raise_api_error(
    *,
    code: str,
    message: str,
    stage: str,
    http_status: int,
    cause: Exception,
) -> None:
    raise HTTPException(
        status_code=http_status,
        detail={
            "code": code,
            "message": message,
            "stage": stage,
        },
    ) from cause


@router.post(
    "/query",
    response_model=AnalyticalResponseSchema,
)
def query_analytics(
    request: AnalyticalQuestionRequest,
    application: AnalyticsApplication = Depends(
        get_analytics_application
    ),
) -> dict:
    """Execute one natural-language analytical query."""

    try:
        response = application.query(request.question)
    except InvalidQuestionError as exc:
        _raise_api_error(
            code="INVALID_QUESTION",
            message=str(exc),
            stage="parsing",
            http_status=status.HTTP_422_UNPROCESSABLE_CONTENT,
            cause=exc,
        )
    except (
        LLMResponseFormatError,
        LLMResponseValidationError,
    ) as exc:
        _raise_api_error(
            code="INVALID_LLM_RESPONSE",
            message=str(exc),
            stage="parsing",
            http_status=status.HTTP_422_UNPROCESSABLE_CONTENT,
            cause=exc,
        )
    except LLMCallError as exc:
        _raise_api_error(
            code="LLM_CALL_FAILED",
            message="Unable to process the analytical question.",
            stage="parsing",
            http_status=status.HTTP_502_BAD_GATEWAY,
            cause=exc,
        )
    except SemanticResolutionError as exc:
        _raise_api_error(
            code="SEMANTIC_RESOLUTION_FAILED",
            message=str(exc),
            stage="semantic_resolution",
            http_status=status.HTTP_422_UNPROCESSABLE_CONTENT,
            cause=exc,
        )
    except QueryPlanningLimitError as exc:
        _raise_api_error(
            code="QUERY_LIMIT_EXCEEDED",
            message=str(exc),
            stage="query_planning",
            http_status=status.HTTP_400_BAD_REQUEST,
            cause=exc,
        )
    except SQLBuilderError as exc:
        _raise_api_error(
            code="QUERY_BUILD_FAILED",
            message=str(exc),
            stage="query_building",
            http_status=status.HTTP_400_BAD_REQUEST,
            cause=exc,
        )
    except DatabaseConnectionError as exc:
        _raise_api_error(
            code="DATABASE_CONNECTION_FAILED",
            message="Unable to connect to the analytics database.",
            stage="query_execution",
            http_status=status.HTTP_502_BAD_GATEWAY,
            cause=exc,
        )
    except QueryExecutionFailedError as exc:
        _raise_api_error(
            code="QUERY_EXECUTION_FAILED",
            message="Unable to execute the analytical query.",
            stage="query_execution",
            http_status=status.HTTP_502_BAD_GATEWAY,
            cause=exc,
        )

    return response.to_dict()
