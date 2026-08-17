"""
Alembic environment script.

Deliberately does NOT read sqlalchemy.url from alembic.ini. Instead it
builds the URL from AIBI_DB_* environment variables (via
database.connection.build_database_url), so local dev, CI, and
production all use the same alembic.ini and differ only in environment
configuration — never in committed files.
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

# Make the project root importable (so `database.*` resolves) regardless
# of the working directory alembic is invoked from.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

load_dotenv()  # loads .env in local/dev; no-op if absent (e.g. in prod/CI)

from database.base import Base  # noqa: E402
from database.connection import build_database_url  # noqa: E402
import database.models  # noqa: E402,F401  (registers ORM models onto Base.metadata)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Autogenerate diffs ORM models (raw/staging/core tables as they're added)
# against the live database. Schema-only migrations (like 001) are still
# hand-written since CREATE SCHEMA has no ORM equivalent.
target_metadata = Base.metadata

# All tables live in the raw/staging/core/analytics schemas, never in
# "public" — so Alembic must be told to manage those schemas explicitly.
MANAGED_SCHEMAS = ["raw", "staging", "core", "analytics"]


def include_schemas(name, type_, parent_names):
    """Restrict autogenerate to the schemas this project owns.

    Prevents Alembic from trying to diff or drop unrelated schemas/tables
    that might exist in a shared database instance.
    """
    if type_ == "schema":
        return name in MANAGED_SCHEMAS
    return True


def run_migrations_offline() -> None:
    """Run migrations without a live DB connection, emitting SQL only."""
    url = build_database_url().render_as_string(hide_password=False)
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        include_name=include_schemas,
        version_table_schema="public",
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live database connection."""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = build_database_url().render_as_string(hide_password=False)

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            include_name=include_schemas,
            version_table_schema="public",
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
