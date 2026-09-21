from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from etl.data_quality.models import DataQualityResult


@dataclass(frozen=True)
class PostgresTypeSpec:
    """Normalized PostgreSQL type properties used by schema validation."""

    base_type: str
    length: int | None = None
    precision: int | None = None
    scale: int | None = None
    timezone: bool | None = None


_TYPE_PATTERN = re.compile(r"^(?P<name>[a-z ]+?)(?:\((?P<args>[^)]+)\))?$")
_TYPE_ALIASES = {
    "character varying": "varchar",
    "varchar": "varchar",
    "int2": "smallint",
    "smallint": "smallint",
    "int4": "integer",
    "integer": "integer",
    "int8": "bigint",
    "bigint": "bigint",
    "bool": "boolean",
    "boolean": "boolean",
    "timestamptz": "timestamp",
    "timestamp with time zone": "timestamp",
    "timestamp without time zone": "timestamp",
}


def _parse_postgresql_type(type_text: str) -> PostgresTypeSpec:
    """Parse SQLAlchemy/information-schema type text into comparable properties."""
    normalized = " ".join(type_text.lower().strip().split())
    match = _TYPE_PATTERN.match(normalized)
    if not match:
        return PostgresTypeSpec(base_type=normalized)

    raw_name = match.group("name").strip()
    base_type = _TYPE_ALIASES.get(raw_name, raw_name)
    raw_args = match.group("args")
    args = tuple(int(value.strip()) for value in raw_args.split(",")) if raw_args else ()

    if base_type == "varchar":
        return PostgresTypeSpec(
            base_type=base_type,
            length=args[0] if args else None,
        )
    if base_type == "numeric":
        return PostgresTypeSpec(
            base_type=base_type,
            precision=args[0] if args else None,
            scale=args[1] if len(args) > 1 else None,
        )
    if base_type == "timestamp":
        return PostgresTypeSpec(
            base_type=base_type,
            timezone="with time zone" in raw_name or raw_name == "timestamptz",
        )
    return PostgresTypeSpec(base_type=base_type)


def _sqlalchemy_type_spec(type_value: object) -> PostgresTypeSpec:
    """Extract semantic properties from a reflected SQLAlchemy type."""
    type_text = str(type_value)
    normalized = " ".join(type_text.lower().strip().split())

    if normalized.startswith("timestamp"):
        return PostgresTypeSpec(
            base_type="timestamp",
            timezone=bool(getattr(type_value, "timezone", False)),
        )
    if normalized.startswith(("varchar", "character varying")):
        return PostgresTypeSpec(
            base_type="varchar",
            length=getattr(type_value, "length", None),
        )
    if normalized.startswith("numeric"):
        return PostgresTypeSpec(
            base_type="numeric",
            precision=getattr(type_value, "precision", None),
            scale=getattr(type_value, "scale", None),
        )
    return _parse_postgresql_type(type_text)


def _postgres_types_match(actual: object, expected: str) -> bool:
    """Compare PostgreSQL types without discarding meaningful constraints."""
    actual_spec = _sqlalchemy_type_spec(actual)
    expected_spec = _parse_postgresql_type(expected)

    if actual_spec.base_type != expected_spec.base_type:
        return False
    if expected_spec.length is not None and actual_spec.length != expected_spec.length:
        return False
    if expected_spec.precision is not None and actual_spec.precision != expected_spec.precision:
        return False
    if expected_spec.scale is not None and actual_spec.scale != expected_spec.scale:
        return False
    if expected_spec.timezone is not None and actual_spec.timezone != expected_spec.timezone:
        return False
    return True


def _normalize_table_reference(table_name: str) -> tuple[str | None, str]:
    """Normalize a schema-qualified table name into (schema, table)."""
    if "." in table_name:
        schema_name, raw_table = table_name.split(".", 1)
        return schema_name, raw_table
    return None, table_name


def _inspector_for_session(session: Session):
    """Return a SQLAlchemy inspector bound to the session's engine."""
    if hasattr(session, "bind") and session.bind is not None:
        return inspect(session.bind)
    if hasattr(session, "engine") and session.engine is not None:
        return inspect(session.engine)
    return inspect(session)


def table_exists_check(session: Session, table_name: str) -> DataQualityResult:
    """Validate that a named database table exists."""
    schema_name, table_ref = _normalize_table_reference(table_name)
    inspector = _inspector_for_session(session)
    exists = inspector.has_table(table_ref, schema=schema_name)

    if exists:
        return DataQualityResult(
            check_name=f"table_exists:{table_name}",
            status="PASS",
            severity="INFO",
            message=f"Table '{table_name}' exists.",
        )

    return DataQualityResult(
        check_name=f"table_exists:{table_name}",
        status="FAIL",
        severity="ERROR",
        affected_rows=1,
        message=f"Table '{table_name}' is missing.",
    )


def view_exists_check(session: Session, view_name: str) -> DataQualityResult:
    """Validate that a named database view exists."""
    schema_name, view_ref = _normalize_table_reference(view_name)
    inspector = _inspector_for_session(session)
    view_names = inspector.get_view_names(schema=schema_name)
    exists = view_ref in view_names

    if exists:
        return DataQualityResult(
            check_name=f"view_exists:{view_name}",
            status="PASS",
            severity="INFO",
            message=f"View '{view_name}' exists.",
        )

    return DataQualityResult(
        check_name=f"view_exists:{view_name}",
        status="FAIL",
        severity="ERROR",
        affected_rows=1,
        message=f"View '{view_name}' is missing.",
    )


def columns_exist_check(
    session: Session,
    table_name: str,
    required_columns: list[str],
) -> DataQualityResult:
    """Validate that all required columns exist in a table."""
    schema_name, table_ref = _normalize_table_reference(table_name)
    inspector = _inspector_for_session(session)
    if not inspector.has_table(table_ref, schema=schema_name):
        return DataQualityResult(
            check_name=f"columns_exist:{table_name}",
            status="FAIL",
            severity="ERROR",
            affected_rows=len(required_columns),
            message=f"Table '{table_name}' is missing; column validation cannot run.",
        )
    columns = inspector.get_columns(table_ref, schema=schema_name)
    existing = {column["name"] for column in columns}
    missing = [column for column in required_columns if column not in existing]

    if not missing:
        return DataQualityResult(
            check_name=f"columns_exist:{table_name}",
            status="PASS",
            severity="INFO",
            message=f"All required columns for '{table_name}' are present.",
        )

    return DataQualityResult(
        check_name=f"columns_exist:{table_name}",
        status="FAIL",
        severity="ERROR",
        affected_rows=len(missing),
        message=f"Missing columns in '{table_name}': {', '.join(missing)}.",
    )


def expected_column_types_check(
    session: Session,
    table_name: str,
    expected_types: dict[str, str],
) -> DataQualityResult:
    """Validate that expected PostgreSQL column types match the live schema."""
    schema_name, table_ref = _normalize_table_reference(table_name)
    inspector = _inspector_for_session(session)
    if not inspector.has_table(table_ref, schema=schema_name):
        return DataQualityResult(
            check_name=f"expected_types:{table_name}",
            status="FAIL",
            severity="ERROR",
            affected_rows=len(expected_types),
            message=f"Table '{table_name}' is missing; expected type validation cannot run.",
        )
    columns = inspector.get_columns(table_ref, schema=schema_name)
    actual_types = {column["name"]: column["type"] for column in columns}

    mismatches: list[str] = []
    for column_name, expected_type in expected_types.items():
        actual_type = actual_types.get(column_name)
        if actual_type is None:
            mismatches.append(f"{column_name}: missing")
            continue
        if not _postgres_types_match(actual_type, expected_type):
            mismatches.append(f"{column_name}: {actual_type} != {expected_type}")

    if not mismatches:
        return DataQualityResult(
            check_name=f"expected_types:{table_name}",
            status="PASS",
            severity="INFO",
            message=f"Column types for '{table_name}' match the expected schema.",
        )

    return DataQualityResult(
        check_name=f"expected_types:{table_name}",
        status="FAIL",
        severity="ERROR",
        affected_rows=len(mismatches),
        message=(
            f"Type mismatches found in '{table_name}': "
            + "; ".join(mismatches)
        ),
    )


def required_not_null_columns_check(
    session: Session,
    table_name: str,
    required_columns: list[str],
) -> DataQualityResult:
    """Validate that required columns are not nullable in the live schema."""
    schema_name, table_ref = _normalize_table_reference(table_name)
    inspector = _inspector_for_session(session)
    if not inspector.has_table(table_ref, schema=schema_name):
        return DataQualityResult(
            check_name=f"required_not_null:{table_name}",
            status="FAIL",
            severity="ERROR",
            affected_rows=len(required_columns),
            message=f"Table '{table_name}' is missing; non-null validation cannot run.",
        )
    columns = inspector.get_columns(table_ref, schema=schema_name)
    nullable_map = {column["name"]: column["nullable"] for column in columns}

    missing = [column for column in required_columns if column not in nullable_map]
    non_nullable = [
        column for column in required_columns if column in nullable_map and nullable_map[column] is False
    ]
    nullable_violations = [
        column for column in required_columns if column in nullable_map and nullable_map[column] is True
    ]

    if not missing and not nullable_violations:
        return DataQualityResult(
            check_name=f"required_not_null:{table_name}",
            status="PASS",
            severity="INFO",
            message=f"All required non-null columns for '{table_name}' are configured correctly.",
        )

    message_parts: list[str] = []
    if missing:
        message_parts.append(f"missing columns: {', '.join(missing)}")
    if nullable_violations:
        message_parts.append(f"nullable columns: {', '.join(nullable_violations)}")

    return DataQualityResult(
        check_name=f"required_not_null:{table_name}",
        status="FAIL",
        severity="ERROR",
        affected_rows=len(nullable_violations) + len(missing),
        message=f"Schema nullability issues in '{table_name}': {'; '.join(message_parts)}.",
    )


def nullability_check(
    session: Session,
    table_name: str,
    column_name: str,
    allow_null: bool = False,
) -> DataQualityResult:
    """Check whether a column contains unexpected NULL values."""
    if not allow_null:
        query = text(
            f"SELECT COUNT(*) FROM {table_name} WHERE {column_name} IS NULL"
        )
        result = session.execute(query).scalar_one()

        if result == 0:
            return DataQualityResult(
                check_name=f"nullability:{table_name}.{column_name}",
                status="PASS",
                severity="INFO",
                message=f"Column '{table_name}.{column_name}' has no NULL values.",
            )

        return DataQualityResult(
            check_name=f"nullability:{table_name}.{column_name}",
            status="WARNING",
            severity="WARNING",
            affected_rows=int(result),
            message=(
                f"Column '{table_name}.{column_name}' contains {result} NULL values."
            ),
        )

    return DataQualityResult(
        check_name=f"nullability:{table_name}.{column_name}",
        status="PASS",
        severity="INFO",
        message=f"Nullability is explicitly allowed for '{table_name}.{column_name}'.",
    )
