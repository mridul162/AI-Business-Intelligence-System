from __future__ import annotations

from uuid import uuid4

from etl.analytics.context.request_context import (
    RequestContext,
    get_request_context,
    reset_request_context,
    set_request_context,
)


def test_get_request_context_returns_none_by_default():
    assert get_request_context() is None


def test_set_request_context_stores_context():
    request_id = uuid4()
    context = RequestContext(request_id=request_id)

    token = set_request_context(context)

    try:
        assert get_request_context() == context
        assert get_request_context().request_id == request_id # type: ignore
    finally:
        reset_request_context(token)


def test_reset_request_context_restores_previous_context():
    request_id = uuid4()
    context = RequestContext(request_id=request_id)

    token = set_request_context(context)

    try:
        assert get_request_context() == context
    finally:
        reset_request_context(token)

    assert get_request_context() is None


def test_nested_context_restores_previous_context():
    outer_context = RequestContext(request_id=uuid4())
    inner_context = RequestContext(request_id=uuid4())

    outer_token = set_request_context(outer_context)

    try:
        assert get_request_context() == outer_context

        inner_token = set_request_context(inner_context)

        try:
            assert get_request_context() == inner_context
        finally:
            reset_request_context(inner_token)

        assert get_request_context() == outer_context
    finally:
        reset_request_context(outer_token)

    assert get_request_context() is None


def test_request_context_is_immutable():
    context = RequestContext(request_id=uuid4())

    try:
        context.request_id = uuid4() # type: ignore
    except AttributeError:
        pass
    else:
        raise AssertionError("RequestContext should be immutable.")