-- Run this once against the aibi_test_db database created by
-- 01_create_test_role_and_db.sql:
--
--   psql -U postgres -h localhost -d aibi_test_db -f 02_seed_integration_test_data.sql
--
-- Safe to re-run: drops and recreates the tables/views each time, so
-- the integration test always starts from a known, exact dataset --
-- the assertions in test_integration_full_stack.py depend on these
-- EXACT values (do not change the seed rows without updating the
-- test's expected sums).
--
-- Mirrors what the metric registry expects, across THREE distinct
-- source views so the multi-query paths (SPLIT_METRICS /
-- COMPARE_METRICS / SIDE_BY_SIDE) are genuinely exercised, not just
-- the single-QueryPlan path.

CREATE SCHEMA IF NOT EXISTS analytics;

-- ---- gross_sales lives on analytics.v_sales -------------------------
DROP TABLE IF EXISTS core_fact_sales CASCADE;
CREATE TABLE core_fact_sales (
    id SERIAL PRIMARY KEY,
    product_category TEXT NOT NULL,
    gross_sales NUMERIC(12, 2) NOT NULL,
    sale_date DATE NOT NULL
);

CREATE OR REPLACE VIEW analytics.v_sales AS
    SELECT product_category, gross_sales, sale_date
    FROM core_fact_sales;

INSERT INTO core_fact_sales (product_category, gross_sales, sale_date) VALUES
    ('Nuts',   1000.00, '2026-01-15'),
    ('Nuts',    500.00, '2026-02-10'),
    ('Snacks',  750.25, '2026-01-20'),
    ('Snacks',  900.00, '2026-02-05');

-- ---- total_expenses lives on analytics.v_expenses -------------------
DROP TABLE IF EXISTS core_fact_expenses CASCADE;
CREATE TABLE core_fact_expenses (
    id SERIAL PRIMARY KEY,
    expense_category TEXT NOT NULL,
    amount NUMERIC(12, 2) NOT NULL,
    expense_date DATE NOT NULL
);

CREATE OR REPLACE VIEW analytics.v_expenses AS
    SELECT expense_category, amount, expense_date
    FROM core_fact_expenses;

INSERT INTO core_fact_expenses (expense_category, amount, expense_date) VALUES
    ('Rent',     300.00, '2026-01-05'),
    ('Utilities', 60.00, '2026-01-18'),
    ('Rent',     300.00, '2026-02-05');

-- ---- cash_in / cash_out share analytics.v_cash_transactions ---------
-- but have conflicting registry fixed filters (direction = 'IN' /
-- 'OUT'), which is exactly why the planner emits SPLIT_METRICS for
-- them rather than one QueryPlan.
DROP TABLE IF EXISTS core_fact_cash_transactions CASCADE;
CREATE TABLE core_fact_cash_transactions (
    id SERIAL PRIMARY KEY,
    amount NUMERIC(12, 2) NOT NULL,
    direction TEXT NOT NULL,
    transaction_date DATE NOT NULL
);

CREATE OR REPLACE VIEW analytics.v_cash_transactions AS
    SELECT amount, direction, transaction_date
    FROM core_fact_cash_transactions;

INSERT INTO core_fact_cash_transactions (amount, direction, transaction_date) VALUES
    (10000.00, 'IN',  '2026-01-10'),
    (12000.00, 'IN',  '2026-02-10'),
    (7000.00,  'OUT', '2026-01-12'),
    -- Deliberately NO February 'OUT' row -> exercises the merger's
    -- "missing key -> 0" rule against a genuinely absent row.
    (5000.00,  'OUT', '2026-03-01');

GRANT USAGE ON SCHEMA analytics TO aibi_test;
GRANT SELECT ON ALL TABLES IN SCHEMA analytics TO aibi_test;
GRANT USAGE ON SCHEMA public TO aibi_test;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO aibi_test;