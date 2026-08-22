# AI Business Intelligence System

An end-to-end AI-powered Business Intelligence system designed to transform operational business data into a validated analytical warehouse and enable natural language access to business metrics.

The system is being built with a layered architecture that separates:

- Source and staging data
- Data warehouse dimensions and facts
- Data validation and financial reconciliation
- Semantic and analytics views
- Metric definitions and analytical queries
- Natural language understanding
- Semantic resolution
- Query generation and execution

The current implementation has completed the warehouse, validation, analytics, metric, and initial natural language query layers.

---

# Project Architecture

```text
Business Data Sources
        │
        ▼
┌──────────────────────┐
│     Raw Layer        │
│  Source ingestion    │
│  Ingestion batches   │
└──────────────────────┘
        │
        ▼
┌──────────────────────┐
│    Staging Layer     │
│ Cleaned source data  │
│ Validation status    │
│ Source metadata     │
└──────────────────────┘
        │
        ▼
┌──────────────────────┐
│  Warehouse Layer     │
│ Dimensions + Facts   │
└──────────────────────┘
        │
        ▼
┌──────────────────────┐
│ Validation &         │
│ Reconciliation       │
└──────────────────────┘
        │
        ▼
┌──────────────────────┐
│ Semantic / Analytics │
│ Views                │
└──────────────────────┘
        │
        ▼
┌──────────────────────┐
│ BI Metrics &         │
│ Analytical Query     │
│ Layer                │
└──────────────────────┘
        │
        ▼
┌──────────────────────┐
│ Natural Language     │
│ Query Layer          │
│ Phase 9              │
└──────────────────────┘
        │
        ▼
┌──────────────────────┐
│ Semantic Resolution  │
│ Next: Phase 9.3      │
└──────────────────────┘
````

---

# Technology Stack

* Python
* PostgreSQL
* SQLAlchemy
* Alembic
* Pydantic
* OpenAI / LLM integration
* Pytest / Unit Testing

---

# Project Progress

## Phase 1–5 — Data Pipeline and Warehouse Foundation

The system foundation was built around a layered data architecture.

### Raw Layer

The raw layer is responsible for preserving source data and ingestion metadata.

Key concepts include:

* Source system tracking
* Source table tracking
* Source row identifiers
* Ingestion batches
* Source hashes
* Ingestion timestamps

This provides data lineage and supports traceability from warehouse records back to their source records.

---

### Staging Layer

Operational data is loaded into staging tables before entering the warehouse.

Staging records include metadata such as:

```text
source_system
source_table
source_row_identifier
ingestion_batch_id
ingested_at
source_hash
record_status
validation_error
```

The staging layer acts as the controlled boundary between source data and the analytical warehouse.

---

# Phase 5 — Data Warehouse

A dimensional warehouse was implemented using business dimensions and transactional fact tables.

## Dimension Tables

The following dimensions are available:

```text
core.dim_date
core.dim_customer
core.dim_product
core.dim_supplier
core.dim_partner
core.dim_cash_account
core.dim_location
```

### Date Dimension

The date dimension provides:

* Date key
* Date
* Year
* Quarter
* Month
* Month number
* Month name
* Week
* Day
* Day name
* Weekend indicator

The warehouse date range currently starts from:

```text
2026-08-01
```

and extends through:

```text
2035-12-31
```

This avoids generating unnecessary analytical dates before the actual beginning of business data.

---

## Fact Tables

All planned warehouse fact tables have been completed.

```text
1.  fact_orders            ✅
2.  fact_sales             ✅
3.  fact_payments          ✅
4.  fact_returns           ✅
5.  fact_return_items      ✅

6.  fact_purchases         ✅
7.  fact_cash_transactions ✅
8.  fact_expenses          ✅
9.  fact_partner_capital   ✅
10. fact_stock_movements   ✅
```

### Warehouse Fact Domains

The warehouse currently supports analytical data for:

* Orders
* Sales
* Payments
* Customer returns
* Return items
* Purchases
* Cash transactions
* Expenses
* Partner capital
* Stock movements

Each fact loader maps staging records to warehouse surrogate keys and preserves source lineage metadata.

---

# Warehouse Loading

Warehouse loaders are responsible for:

1. Reading pending staging records
2. Resolving dimension keys
3. Deduplicating source records where required
4. Loading warehouse fact records
5. Performing upserts where appropriate
6. Preserving ingestion metadata

The fact loading process handles duplicate source records before executing `INSERT ... ON CONFLICT` operations.

This prevents PostgreSQL errors where multiple rows in the same insert operation attempt to update the same unique warehouse record.

---

# Phase 6 — Warehouse Validation & Reconciliation

A dedicated validation layer was implemented after completing the warehouse.

The validation process verifies three major areas.

## 1. Dimension Validation

Each dimension is checked for:

* Expected record count
* Actual warehouse record count
* Duplicate business identifiers

Validated dimensions:

```text
dim_customer
dim_product
dim_supplier
dim_partner
dim_cash_account
dim_location
```

---

## 2. Fact Validation

Each fact table is checked for:

* Expected source record count
* Actual warehouse record count
* Duplicate business identifiers

Validated facts:

```text
fact_orders
fact_sales
fact_payments
fact_returns
fact_return_items
fact_purchases
fact_cash_transactions
fact_expenses
fact_partner_capital
fact_stock_movements
```

---

## 3. Financial Reconciliation

Financial totals are reconciled between the staging/source layer and the warehouse.

Current reconciliation includes:

```text
order_total_amount
payment_amount
return_refund_amount
purchase_line_total
expense_amount
cash_transaction_amount
```

A successful validation run produced:

```text
FINAL STATUS: PASS — Warehouse validation completed successfully.
```

The validation report confirmed:

* All dimension counts matched
* All fact counts matched
* No duplicate identifiers were found
* Financial totals reconciled with zero difference

---

# Phase 7 — Semantic / Analytics Layer

The warehouse tables are exposed through business-friendly analytics views.

These views hide warehouse surrogate-key complexity and provide stable analytical interfaces for reporting and the AI query layer.

## Analytics Views

The following views were created and verified successfully:

```text
analytics.v_orders
analytics.v_sales
analytics.v_payments
analytics.v_returns
analytics.v_return_items
analytics.v_purchases
analytics.v_cash_transactions
analytics.v_expenses
analytics.v_partner_capital
analytics.v_stock_movements
analytics.v_daily_business_summary
```

---

## `analytics.v_orders`

Provides order-level analytical data.

Includes concepts such as:

* Order ID
* Order date
* Customer information
* Subtotal
* Invoice discount
* Delivery charge
* Total amount
* Order status
* Collection information

---

## `analytics.v_sales`

Provides sales-line analytical data.

This is the product-level sales view and exposes business concepts required for product and sales analysis.

Examples include:

* Order information
* Product information
* Quantity
* Unit price
* Gross sales
* Unit cost
* Cost of goods sold
* Sales-related dimensions

---

## `analytics.v_payments`

Provides payment analytics including:

* Payment date
* Order reference
* Customer
* Cash account
* Payment amount
* Payment method
* Collector
* Notes

---

## `analytics.v_returns`

Provides return-level analytics for:

* Customer returns
* Supplier returns
* Order or purchase references
* Customer information
* Location
* Cash account
* Refund amount
* Due adjustment
* Cash refund
* Return reason
* Return status

---

## `analytics.v_return_items`

Provides product-level returned-item analysis.

Includes:

* Return information
* Product information
* Quantity
* Line amount
* Returned COGS
* Location inherited from the parent return

---

## `analytics.v_purchases`

Provides purchase-line analytics including:

* Purchase date
* Supplier
* Product
* Location
* Quantity
* Unit cost
* Item discount
* Line total

---

## `analytics.v_cash_transactions`

Provides cash-flow analytics.

The view exposes the actual transaction direction:

```text
IN
OUT
```

This is used for cash-flow calculations rather than incorrectly inferring direction from transaction type.

---

## `analytics.v_expenses`

Provides expense analytics including:

* Expense category
* Amount
* Cash account
* Reference
* Creation information

---

## `analytics.v_partner_capital`

Provides analytics for partner capital transactions, including:

* Partner
* Capital transaction
* Reference ID
* Cash account
* Created by
* Creation timestamp

---

## `analytics.v_stock_movements`

Provides inventory movement analytics.

The view supports analysis of:

* Product
* Movement direction
* Quantity
* Source location
* Destination location
* Inventory movement references

---

## `analytics.v_daily_business_summary`

Provides a daily business-level summary.

Current metrics include:

```text
total_orders
total_sales
total_payments

total_returns
total_return_amount
total_cash_refund
total_due_adjustment

total_purchases
total_purchase_amount

net_sales
gross_business_margin

cash_in
cash_out
```

The cash-flow logic correctly uses the `direction` field for:

```text
direction = 'IN'
direction = 'OUT'
```

The daily summary was also aligned with the actual business data start date.

---

# Phase 8 — BI Metrics & Analytical Query Layer

Phase 8 established a machine-readable semantic layer on top of the analytics views.

The purpose is to define analytical metrics once and allow later layers to safely build queries using those definitions.

The architecture separates:

```text
Metric Definition
        ↓
Metric Registry
        ↓
Query Request
        ↓
Query Builder
        ↓
Validated SQL
        ↓
PostgreSQL
```

---

## Phase 8.1 — Metric Catalog

Metrics were defined with explicit analytical contracts.

Each metric definition specifies:

1. SQL source view
2. Aggregation expression
3. Supported filters
4. Supported dimensions
5. Supported time grains
6. Output field names
7. Edge-case rules

This prevents the natural language layer from directly inventing SQL or database logic.

---

## Machine-Readable Metric Definitions

Metrics are represented as structured definitions.

A metric definition conceptually contains:

```text
Metric Name
Description
Source View
Aggregation
Filters
Dimensions
Time Grains
Output Fields
Edge-Case Rules
```

The metric registry acts as the canonical source of truth for valid analytical metrics.

---

## Analytical Query Layer

A structured analytical query layer was implemented to translate validated requests into database queries.

The system supports analytical concepts such as:

* Metrics
* Dimensions
* Filters
* Time ranges
* Time grains
* Sorting
* Limits

The query layer is designed so that downstream natural language processing does not directly generate arbitrary SQL.

Instead:

```text
Natural Language
        ↓
Structured Request
        ↓
Metric Resolution
        ↓
Validation
        ↓
Query Builder
        ↓
SQL
```

---

## Test Queries

A dedicated analytics test query runner was created:

```text
etl/analytics/run_test_queries.py
```

This allows the analytical layer to be tested directly against the database before connecting it to an LLM.

---

# Phase 9 — Natural Language → Analytical Query Layer

The system is currently implementing the natural language interface for analytical queries.

The goal is to convert questions such as:

```text
What were my total sales this month?
```

into a structured analytical request rather than immediately generating SQL.

---

# Phase 9.1 — Analytical Query Contract

Completed.

A structured schema was defined for representing the intent of an analytical question.

The contract supports:

* Primary metric
* Additional metrics
* Dimensions
* Filters
* Filter operators
* Time grains
* Time ranges
* Relative time presets
* Absolute dates
* Sorting
* Limits
* Comparison modes

A conceptual request looks like:

```json
{
  "metric": "total_sales",
  "additional_metrics": [
    "total_payments"
  ],
  "dimensions": [],
  "filters": [],
  "time_grain": "monthly",
  "time_range": {
    "preset": null,
    "label": null,
    "start": "2026-08-01",
    "end": "2026-08-31"
  },
  "limit": null,
  "sort_by": null,
  "sort_order": null,
  "comparison": null
}
```

The analytical query contract acts as the boundary between natural language understanding and the downstream analytical query system.

---

# Phase 9.2 — Natural Language Query Parser

Completed.

An LLM-based parser was implemented to convert natural language questions into validated structured requests.

## Parser Responsibilities

The parser:

1. Accepts a natural language business question
2. Builds a grounded system prompt
3. Calls an abstracted LLM completion function
4. Extracts JSON from the response
5. Handles JSON code fences or surrounding prose
6. Validates the response
7. Converts the response into an `AnalyticalQueryRequest`
8. Preserves the original user question

The parser does **not**:

* Generate SQL
* Execute SQL
* Calculate business metrics
* Validate metric names against the registry
* Resolve metric aliases to database fields

These responsibilities belong to later phases.

---

## Prompt Construction

System prompt construction is separated from the parser implementation.

This makes prompt text independently reviewable and easier to iterate without changing the parser plumbing.

The prompt includes:

* Required JSON response format
* Known time grains
* Known relative time presets
* Known filter operators
* Known comparison modes
* Optional metric hints
* Optional dimension hints
* Current date for relative-date interpretation

The prompt distinguishes between:

### Absolute periods

Examples:

```text
August 2026
August 1, 2026
Q3 2026
```

For unambiguous absolute periods, the parser may return:

```text
time_range.start
time_range.end
```

### Relative periods

Examples:

```text
today
yesterday
this month
last month
last week
last 30 days
```

For relative periods, the parser returns a preset rather than calculating dates directly.

Example:

```json
{
  "time_range": {
    "preset": "current_month"
  }
}
```

Actual date resolution is intentionally deferred to a later phase.

---

## LLM Abstraction

The parser uses an abstraction around the LLM completion call.

Conceptually:

```text
NLQueryParser
      │
      ▼
complete(system_prompt, question)
      │
      ▼
LLM Response
```

This allows deterministic testing without requiring a real LLM.

Unit tests use fake completion functions returning predefined responses.

---

## Response Handling

The parser supports responses such as:

### Raw JSON

```json
{"metric": "total_sales"}
```

### JSON inside a code fence

````text
```json
{"metric": "total_sales"}
````

````

### JSON surrounded by prose

```text
Sure! Here you go:

{"metric": "total_sales"}

Hope that helps.
````

The parser extracts and validates the JSON object before converting it into the analytical query contract.

---

## Error Handling

The parser includes structured errors for:

* Invalid questions
* Empty questions
* LLM call failures
* Empty LLM responses
* Invalid response format
* Non-JSON responses
* JSON arrays instead of objects
* Missing metrics
* Empty metrics
* Invalid filter operators
* Invalid filter structures
* Invalid comparison modes
* Invalid dates
* Invalid time grains
* Invalid time-range combinations

---

## Parser and Semantic Resolution Boundary

An important architectural decision is that parsing and semantic validation remain separate.

The parser can produce:

```text
metric = "sales"
```

or even:

```text
metric = "definitely_not_a_real_metric"
```

without checking the metric registry.

This is intentional.

The architecture is:

```text
Natural Language Question
        │
        ▼
Phase 9.2
NL Query Parser
        │
        ▼
Structured AnalyticalQueryRequest
        │
        ▼
Phase 9.3
Semantic Resolver
        │
        ▼
Canonical Metric / Dimension
        │
        ▼
Analytical Query Layer
```

This separation prevents the LLM parsing layer from becoming tightly coupled to the warehouse metric registry.

---

# Testing

The project currently has a comprehensive automated test suite.

Latest successful result:

```text
146 passed, 168 subtests passed in 0.35s
```

Tests currently cover areas including:

* Analytical query schemas
* Time ranges
* Relative presets
* Filters
* Sorting
* Comparison modes
* Prompt construction
* Metric hints
* Dimension hints
* JSON extraction
* Code-fence cleanup
* Response validation
* Error handling
* Parser behavior
* LLM abstraction
* Parser/registry separation

---

# Current Architecture

```text
┌───────────────────────────────┐
│      Business Data Sources    │
└───────────────┬───────────────┘
                ▼
┌───────────────────────────────┐
│          Raw Layer            │
│  Data lineage + ingestion     │
└───────────────┬───────────────┘
                ▼
┌───────────────────────────────┐
│        Staging Layer          │
│  Validation + normalization   │
└───────────────┬───────────────┘
                ▼
┌───────────────────────────────┐
│       Warehouse Layer         │
│  Dimensions + Fact Tables     │
└───────────────┬───────────────┘
                ▼
┌───────────────────────────────┐
│ Warehouse Validation          │
│ + Financial Reconciliation    │
└───────────────┬───────────────┘
                ▼
┌───────────────────────────────┐
│     Analytics Views           │
│    Semantic Data Layer        │
└───────────────┬───────────────┘
                ▼
┌───────────────────────────────┐
│    Metric Registry            │
│ Machine-Readable BI Metrics   │
└───────────────┬───────────────┘
                ▼
┌───────────────────────────────┐
│   Analytical Query Layer      │
│ Structured Request → SQL      │
└───────────────┬───────────────┘
                ▼
┌───────────────────────────────┐
│ Phase 9.1 + 9.2               │
│ NL → Structured Query         │
│ Parser                        │
└───────────────┬───────────────┘
                ▼
┌───────────────────────────────┐
│ Phase 9.3 — NEXT              │
│ Semantic Resolution           │
└───────────────────────────────┘
```

---

# Current Status

```text
PHASE 1–5 — Data Pipeline & Warehouse Foundation    ✅
PHASE 6   — Warehouse Validation & Reconciliation   ✅
PHASE 7   — Semantic / Analytics Layer              ✅
PHASE 8   — BI Metrics & Analytical Query Layer     ✅

PHASE 9   — Natural Language → Analytical Query Layer

9.1 Analytical Query Contract / Schema              ✅
9.2 NL → Structured Query Parser                    ✅
9.3 Semantic Resolution Layer                       ⏭️ NEXT
9.4 Time Range Resolution                           ⏳
9.5 Analytical Query Validation                     ⏳
9.6 NL → Query Layer Integration                    ⏳
```

---

# Next Step

## Phase 9.3 — Semantic Resolution Layer

The next component will resolve LLM-generated business terms into canonical metric and dimension definitions.

Example:

```text
User Question
        │
        ▼
"Show me sales by product this month"
        │
        ▼
NL Query Parser
        │
        ▼
metric = "sales"
dimensions = ["product"]
        │
        ▼
Semantic Resolver
        │
        ├── sales
        │       ↓
        │   gross_sales
        │
        └── product
                ↓
            product_name
        │
        ▼
Canonical Analytical Request
        │
        ▼
Metric Validation + Query Layer
```

Phase 9.3 will ensure that downstream query generation operates only on canonical, registry-backed business definitions.

---

# Development Principles

The system is being built around several core principles:

### Layered Architecture

Each layer has a clearly defined responsibility.

### Data Lineage

Warehouse records preserve source and ingestion metadata.

### Validation Before Analytics

Data is validated and reconciled before being exposed to analytical and AI layers.

### Registry-Driven Metrics

Business metrics are defined centrally instead of allowing arbitrary SQL definitions.

### Structured LLM Output

Natural language is converted into validated structured data before reaching the query layer.

### Separation of Concerns

The parser, semantic resolver, time resolver, validator, and SQL query layer remain separate components.

### Testability

External dependencies, including LLM calls, are abstracted to allow deterministic automated testing.

### Safe Query Generation

The LLM is not responsible for writing or executing arbitrary SQL.

Instead, the intended architecture is:

```text
Natural Language
      ↓
Structured Intent
      ↓
Semantic Resolution
      ↓
Validation
      ↓
Registry-Guided Query Construction
      ↓
SQL Execution
      ↓
Analytical Result
```

---

# Roadmap

```text
Completed
─────────
✓ Raw and staging data layers
✓ Warehouse dimensions
✓ Warehouse fact tables
✓ Warehouse validation
✓ Financial reconciliation
✓ Analytics views
✓ Metric catalog
✓ Machine-readable metric registry
✓ Analytical query layer
✓ Analytical query testing
✓ Phase 9.1 analytical query contract
✓ Phase 9.2 NL query parser

In Progress
───────────
→ Phase 9.3 semantic resolution

Upcoming
────────
○ Phase 9.4 time range resolution
○ Phase 9.5 analytical query validation
○ Phase 9.6 NL → query layer integration
○ LLM-backed end-to-end analytical querying
○ Analytical result generation
○ API integration
○ Business intelligence interface
```

```
