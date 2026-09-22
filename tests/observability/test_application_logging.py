from __future__ import annotations

from unittest.mock import Mock

import pytest

from etl.analytics.application.analytics_application import AnalyticsApplication
from etl.analytics.response.builder import AnalyticalResponse


def build_application(
    *,
    parser=None,
    semantic_resolver=None,
    query_orchestrator=None,
    response_builder=None,
):
    return AnalyticsApplication(
        parser=parser or Mock(),
        semantic_resolver=semantic_resolver or Mock(),
        query_orchestrator=query_orchestrator or Mock(),
        response_builder=response_builder or Mock(),
        time_resolver=Mock(),
    )


def test_query_logs_started_and_completed(caplog):
    parser = Mock()
    semantic_resolver = Mock()
    query_orchestrator = Mock()
    response_builder = Mock()

    parsed_request = Mock()
    resolved_query = Mock()
    analytical_request = Mock()
    analytical_result = Mock()
    response = Mock(spec=AnalyticalResponse)

    parser.parse.return_value = parsed_request
    semantic_resolver.resolve.return_value = resolved_query
    resolved_query.to_analytical_query_request.return_value = (
        analytical_request
    )
    query_orchestrator.execute.return_value = analytical_result
    response_builder.build.return_value = response

    time_resolver = Mock(return_value=analytical_request)

    application = AnalyticsApplication(
        parser=parser,
        semantic_resolver=semantic_resolver,
        query_orchestrator=query_orchestrator,
        response_builder=response_builder,
        time_resolver=time_resolver,
    )

    with caplog.at_level("INFO"):
        result = application.query("What were our net sales?")

    assert result is response

    messages = [record.message for record in caplog.records]

    assert "analytics_query_started" in messages
    assert "analytics_query_completed" in messages


def test_query_logs_failure(caplog):
    parser = Mock()
    parser.parse.side_effect = ValueError("invalid query")

    application = build_application(parser=parser)

    with caplog.at_level("INFO"):
        with pytest.raises(ValueError, match="invalid query"):
            application.query("invalid question")

    messages = [record.message for record in caplog.records]

    assert "analytics_query_started" in messages
    assert "analytics_query_failed" in messages