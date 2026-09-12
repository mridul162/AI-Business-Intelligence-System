-- Run this once as a Postgres superuser (e.g. the `postgres` role),
-- connected to any existing database (commonly `postgres`):
--
--   psql -U postgres -h localhost -f 01_create_test_role_and_db.sql
--
-- Safe to re-run: skips creation if the role/database already exist.

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'aibi_test') THEN
        CREATE ROLE aibi_test WITH LOGIN PASSWORD 'aibi_test_pw';
    END IF;
END
$$;

-- CREATE DATABASE cannot run inside a DO block/transaction, and
-- Postgres has no "CREATE DATABASE IF NOT EXISTS" -- \gexec is the
-- standard psql idiom for conditional DDL like this.
SELECT 'CREATE DATABASE aibi_test_db OWNER aibi_test'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'aibi_test_db')
\gexec

GRANT ALL PRIVILEGES ON DATABASE aibi_test_db TO aibi_test;