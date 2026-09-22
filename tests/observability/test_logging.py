from __future__ import annotations

import logging
from uuid import uuid4

from etl.analytics.context.request_context import (
    RequestContext,
    reset_request_context,
    set_request_context,
)
from etl.observability.logging import RequestContextFilter


def test_request_context_filter_adds_context_fields():
    request_id = uuid4()
    user_id = uuid4()
    tenant_id = uuid4()

    token = set_request_context(
        RequestContext(
            request_id=request_id,
            user_id=user_id,
            tenant_id=tenant_id,
            role="admin",
        )
    )

    try:
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="test message",
            args=(),
            exc_info=None,
        )

        result = RequestContextFilter().filter(record)

        assert result is True
        assert getattr(record, "request_id") == str(request_id)
        assert getattr(record, "user_id") == str(user_id)
        assert getattr(record, "tenant_id") == str(tenant_id)
    finally:
        reset_request_context(token)


def test_request_context_filter_handles_missing_context():
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="test message",
        args=(),
        exc_info=None,
    )

    result = RequestContextFilter().filter(record)

    assert result is True
    assert getattr(record, "request_id") is None
    assert getattr(record, "user_id") is None
    assert getattr(record, "tenant_id") is None


def test_request_context_filter_handles_unauthenticated_context():
    request_id = uuid4()

    token = set_request_context(
        RequestContext(request_id=request_id)
    )

    try:
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="test message",
            args=(),
            exc_info=None,
        )

        RequestContextFilter().filter(record)

        assert getattr(record, "request_id") == str(request_id)
        assert getattr(record, "user_id") is None
        assert getattr(record, "tenant_id") is None
    finally:
        reset_request_context(token)