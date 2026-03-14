# Coding Agent Session: Greek Municipal Budget Visualization Tool

## What We Built

A full-stack open-data platform that automatically ingests, parses, and visualizes the budget
documents of any of the 332 Greek municipalities — sourced live from the government's
mandatory transparency portal, [Diavgeia](https://diavgeia.gov.gr).

Greece requires every municipality to publish its annual budget and technical program as a
signed PDF on Diavgeia. These PDFs are machine-generated but wildly inconsistent in layout
across municipalities. Until now, the data was effectively inaccessible to citizens — you
could download a 200-page PDF, but you couldn't search, compare, or visualize it.

This session built the tool that changes that.

---

## The Hard Parts

### 1. PDF extraction across inconsistent municipal layouts

Greek budget PDFs use European number formatting (`1.661.761,40`), multilingual Greek text,
and document layouts that vary per municipality — some use proper table structures, others
dump prose with embedded numbers. The extraction pipeline uses **pdfplumber** for structured
pages and falls back to **Claude Haiku** (via the Anthropic API) for pages where pdfplumber
returns fewer than 10 rows. Claude is prompted with a strict JSON schema via `tool_use` to
guarantee structured output with no markdown fragility.

Two document types are supported:
- **BUDGET** (`Προϋπολογισμός / ΔΑΠΑΝΕΣ`): hierarchical KAE expense codes with year-comparison
  columns (ΠΥ 2024, Αναμορφωμένος, ΠΥ 2025, Διαφορά)
- **TECHNICAL_PROGRAM** (`Τεχνικό Πρόγραμμα`): flat infrastructure project listings

### 2. Diavgeia auto-discovery

Rather than requiring users to manually download PDFs, the pipeline includes a REST client
that talks to the Diavgeia API to:
- Resolve any municipality name (Greek text) to its government UID across 332 municipalities
- Search for budget decisions (types Β1, Β2, Ε) for a given year
- Download the PDFs with retry logic

A single command processes an entire municipality:
```bash
python pipeline.py --municipality "Αχαρνές" --year 2025
```

### 3. Unified schema design

A key architectural decision during the session: rather than having separate database tables
for budget categories, budget items, technical projects, and technical project items, we
collapsed everything into a single unified schema:

```
Document → Item (code + description + parentCode) → ItemAmount (label + amount)
```

The KAE code hierarchy (e.g. `00` → `00-60` → `00-603` → `00-6031`) is reconstructed at
render time by truncating the code string — no separate lookup table needed.

This means the loader, API, and frontend all have a single code path for both document types.

### 4. Interactive web frontend

A **Next.js 14** App Router frontend visualizes the loaded data:
- Document list with municipality filter
- Per-document detail page with:
  - Summary cards (total budget, YoY change, category count)
  - Spending bar chart comparing current vs prior year by top-level KAE group
  - Pie chart of ΠΥ 2025 spending breakdown
  - Collapsible budget table with KAE tree indentation and inline % change

Column headers are detected dynamically from the data — no hardcoding for document
format variations across municipalities.

---

## Stack

| Layer | Technology |
|---|---|
| ETL | Python, pdfplumber, Anthropic Claude Haiku |
| Database | PostgreSQL via Docker, Prisma ORM (schema + migrations) |
| Loader | psycopg2 (direct, no ORM coupling in pipeline) |
| Web | Next.js 14 App Router, TypeScript, Recharts |
| Discovery | Diavgeia REST API (Greek gov transparency portal) |

---

## Numbers

- **55 passing unit tests** for transformers (amount parser, KAE parser)
- **180 items loaded** across 3 test municipalities:
  - Αχαρνές: 45 technical program items
  - Παλαιό Φάληρο: 97 budget items
  - Ρόδος: 38 budget items
- **332 municipalities** accessible via Diavgeia auto-discovery

---

## Why This Matters

Greek municipal budget data has been legally public for years but practically inaccessible.
This tool makes it machine-readable and explorable for the first time — a journalist, a
researcher, or a citizen can run one command and get an interactive breakdown of how their
municipality is spending public money.

This was built as a Google Summer of Code proof-of-concept for
[OpenCouncil](https://opencouncil.gr), an open-source civic tech platform for Greek local
government.

---

## Running It

```bash
# Start DB
docker compose up -d postgres

# Load a municipality from Diavgeia (auto-download + extract + store)
cd etl && python pipeline.py --municipality "Αχαρνές" --year 2025

# Start the web app
cd web && npm run dev   # → http://localhost:3000
```
