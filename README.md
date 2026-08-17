# Hasanah Mart AI Business Intelligence — Database Layer

PostgreSQL persistence layer for the AI-BI platform, built from:

```
docs/HBMS_DATA_CONTRACT.md
docs/ANALYTICAL_MODEL.md
docs/SOURCE_TO_ANALYTICAL_MAPPING.md
docs/POSTGRESQL_SCHEMA.md
```

## Structure

```
ai-business-intelligence/
├── docs/                       reference contracts (source of truth for schema decisions)
├── database/
│   ├── connection.py           engine/session management, reads AIBI_DB_* env vars
│   ├── base.py                 shared SQLAlchemy declarative Base + naming convention
│   ├── models/                 ORM models, added incrementally per layer
│   └── migrations/
│       ├── env.py              Alembic environment (env-var driven, schema-aware)
│       ├── script.py.mako      revision template
│       └── versions/
│           └── 001_create_schemas.py
├── alembic.ini
├── requirements.txt
└── .env.example
```

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in AIBI_DB_* values
```

## Running migrations

```bash
# apply all migrations
alembic upgrade head

# preview the SQL without touching a database
alembic upgrade head --sql

# check current DB revision
alembic current

# create the next migration (hand-write DDL, or let autogenerate diff
# ORM models once they exist under database/models/)
alembic revision -m "create ingestion metadata table"
```

## Status

| Step | Migration | Status |
|---|---|---|
| Schemas (raw/staging/core/analytics) | `001_create_schemas` | ✅ done |
| Ingestion metadata (`ingestion_batch`) | `002_create_ingestion_metadata` | ⏳ next |
| Raw tables | `003_create_raw_tables` | pending |
| Staging tables | `004_create_staging_tables` | pending |
| Dimensions | `005_create_dimensions` | pending |
| Fact tables | `006`–`015` | pending |
| Indexes | `016_create_indexes` | pending |
| Analytics views | `017_create_analytics_views` | pending |

Build one migration at a time and validate against a real (or local
throwaway) Postgres instance before moving to the next, per
`POSTGRESQL_SCHEMA.md` §36 — don't generate all layers in one shot.

## Design notes

- **No `sqlalchemy.url` in `alembic.ini`.** The URL is built from
  `AIBI_DB_*` environment variables in `database/migrations/env.py` via
  `database.connection.build_database_url()`, so the same committed
  config works unchanged across local/CI/production.
- **Explicit schema management.** `env.py` restricts Alembic's
  autogenerate to the `raw`/`staging`/`core`/`analytics` schemas only
  (`include_schemas` + `include_name`), so it won't try to diff or drop
  unrelated schemas in a shared database instance.
- **Fixed naming convention** (`database/base.py`) so constraint names
  (`pk_...`, `fk_...`, `uq_...`, `ck_...`, `ix_...`) are deterministic —
  required for autogenerate diffs to be stable across environments.
- **NUMERIC, never float**, for all money/quantity columns, per
  `POSTGRESQL_SCHEMA.md` §3.1.
