from __future__ import annotations

from multiprocessing import connection
from uuid import UUID, uuid4

from fastapi import params
from sqlalchemy.dialects import postgresql

from etl.analytics.context.request_context import TenantScope
from etl.analytics.planner.query_plan import QueryPlan
from etl.analytics.sql.sql_builder import build_query


def test_tenant_scope_is_added_to_the_sql_boundary() -> None:
    tenant_id = uuid4()
    plan = QueryPlan(source_view="analytics.v_sales", metrics=("gross_sales",))

    statement = build_query(
        plan,
        tenant_scope=TenantScope(tenant_id),
    ).statement.compile(dialect=postgresql.dialect())

    sql = str(statement)
    assert "tenant_id" in sql
    assert tenant_id in statement.params.values()

def test_build_query_injects_tenant_predicate() -> None:
    tenant_id = UUID("00000000-0000-0000-0000-000000000001")

    plan = QueryPlan(
        source_view="analytics.v_sales",
        metrics=("gross_sales",),
    )

    built = build_query(
        plan,
        tenant_scope=TenantScope(tenant_id=tenant_id),
    )

    sql = str(
        built.statement.compile(
            compile_kwargs={"literal_binds": False}
        )
    )

    params = built.statement.compile().params

    tenant_params = {
        key: value
        for key, value in params.items()
        if key.startswith("tenant_id")
    }

    assert tenant_params
    assert tenant_id in tenant_params.values()                  