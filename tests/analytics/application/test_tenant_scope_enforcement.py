# tests/analytics/application/test_tenant_scope_enforcement.py
from __future__ import annotations

import pytest

from etl.analytics.application.factory import create_analytics_application
from etl.analytics.config import get_settings
from etl.analytics.context.request_context import (
    reset_request_context,
    set_request_context,
    RequestContext,
)
from etl.analytics.sql.errors import MissingTenantScopeError
from uuid import uuid4


def test_query_without_tenant_context_raises_missing_tenant_scope() -> None:
    """The real production wiring refuses to build an unscoped query
    when no tenant context is available -- this is the regression test
    for the fail-open gap in sql_builder.build_query."""

    app = create_analytics_application(settings=get_settings())

    # Deliberately no request context set at all: this is the exact
    # condition that previously caused build_query to silently omit
    # the tenant filter instead of failing.
    with pytest.raises(MissingTenantScopeError):
        app.query("total sales")


def test_query_with_tenant_context_does_not_raise_missing_tenant_scope() -> None:
    """Sanity check: a request with a real tenant context should not
    trip the new guard (it may still fail later for unrelated reasons
    like DB connectivity in a unit-test environment, so we only assert
    it's not MissingTenantScopeError specifically)."""

    token = set_request_context(
        RequestContext(request_id=uuid4(), user_id=uuid4(), tenant_id=uuid4(), role="analyst")
    )
    try:
        app = create_analytics_application(settings=get_settings())
        try:
            app.query("total sales")
        except MissingTenantScopeError:
            pytest.fail("MissingTenantScopeError raised even though tenant context was set")
        except Exception:
            pass  # any other failure (e.g. no live DB) is out of scope here
    finally:
        reset_request_context(token)