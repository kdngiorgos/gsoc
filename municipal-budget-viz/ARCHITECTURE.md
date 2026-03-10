# Architecture: Municipal Budget Visualization Tool

## What This Is

A proof-of-concept that reads Greek municipal budget PDFs published on
[Diavgeia](https://diavgeia.gov.gr/), extracts structured data with an LLM,
stores it in PostgreSQL, and displays it in a Next.js web app.

Built for the GSoC / OpenCouncil project.

---

## High-Level Flow

```
Diavgeia (API)
    │  discover_and_download()
    ▼
PDF files
    │  pdfplumber.extract_text()  (one chunk per page)
    ▼
LLM (Claude Haiku or Ollama)
    │  structured JSON prompt → validated dicts
    ▼
ETL pipeline (Python)
    │  normalise → flat Item list
    ▼
PostgreSQL  ←──  Prisma schema
    │
    ▼
Next.js API routes  →  Next.js pages  →  Browser
```

---

## PDF Document Types

### BUDGET (`ΔΑΠΑΝΕΣ` / `Τεύχος Προϋπολογισμού`)

A hierarchical expense-code (KAE) ledger.  Each row has a code, a Greek
description, and up to four year-comparison amounts:

| LLM field | Greek label stored in DB | Meaning |
|---|---|---|
| `amount2024` | `ΠΥ 2024` | Previous year budget |
| `amountMidYear` | `Αναμορφωμένος` | Mid-year revised |
| `amount2025` | `ΠΥ 2025` | Current year budget |
| `amountVariance` | `Διαφορά` | Variance (2025 − 2024) |

KAE codes encode a tree by truncation:

```
"00"           → root section
"00-60"        → group     (parent: "00")
"00-603"       → article   (parent: "00-60")
"00-6031"      → sub-item  (parent: "00-603")
"00-6031.0001" → detail    (parent: "00-6031")
```

`parentCode` is derived at extraction time in `budget_extractor._derive_parent_code()`.
No separate lookup table is needed.

### TECHNICAL_PROGRAM (`Τεχνικό Πρόγραμμα`)

A flat list of infrastructure projects.  Each row has a project code, a
description, and two monetary columns:

| Greek label | Meaning |
|---|---|
| `Προϋπολογισμός` | Total approved project budget |
| `Ποσό` | Amount allocated for the current year |

Project codes look like `25-7412.007` or `30-7321.00018`.  They have no
parent-child relationship, so `parentCode` is always `null`.

---

## ETL Pipeline (`etl/`)

### `pipeline.py`

CLI entry point.  Two modes:

**Manual mode** — point at a file or directory:
```bash
python pipeline.py --input path/to/file.pdf --type budget
python pipeline.py --input path/to/dir/   --type auto
```
`--type auto` uses `detect_doc_type()` which checks filename keywords
(`δαπανεσ`, `τεχνικο`, `1_`, `2_`, …) then falls back to reading the first
three pages with pdfplumber.

**Diavgeia mode** — auto-discover PDFs for a municipality:
```bash
python pipeline.py --municipality "Αχαρνές" --year 2025
```
Calls `discovery/diavgeia_client.py`, which queries the Diavgeia REST API,
matches decisions of type Β1/Β2 (budget) and Ε (technical program), downloads
the PDFs, then feeds each one to the same `process_pdf()` function.

For each PDF, `process_pdf()`:
1. Detects year from filename (regex `202\d`)
2. `register_document()` → inserts a `Document` row, returns its `id`
3. Calls `extract_budget()` or `extract_technical()`
4. Calls `load_items(document_id, items)`

### Extractors

#### `text_extractor.py`
Thin wrapper around `pdfplumber`.  Reads all pages and returns a list of
`(page_number, text)` tuples.  Handles corrupt pages gracefully.

#### `ollama_extractor.py`
Contains:
- `_BUDGET_PROMPT` / `_TECHNICAL_PROMPT` — the LLM prompts (used by both Ollama and Claude backends)
- `_validate_budget_item()` / `_validate_project()` — schema validators that parse amounts, reject rows without valid codes, etc.
- `_read_pages()` — shared pdfplumber page reader
- `extract_budget_ollama()` / `extract_technical_ollama()` — Ollama implementations

Amount parsing is done inside `_validate_budget_item` using `transformers/amount_parser.py`
which handles the European format (`"1.661.761,40"` → `Decimal("1661761.40")`).

The Ollama backend uses `format="json"` which enforces valid JSON at the grammar
level.  Model defaults to `qwen2.5:7b`, configurable via `OLLAMA_MODEL` env var.

#### `claude_extractor.py`
Mirrors the Ollama public API but calls `claude-haiku-4-5-20251001` via the
Anthropic Python SDK.  Activated automatically when `ANTHROPIC_API_KEY` is set.

The response is plain JSON text (no `format="json"` equivalent in the Claude
API); the extractor strips any accidental markdown code fences.

If `stop_reason == "max_tokens"` the page is skipped with a warning.
Rate-limit errors (HTTP 429) are retried automatically by the Anthropic SDK.

#### `budget_extractor.py`

Calls the LLM backend, filters subtotal rows (matching `σύνολ[οα]|άθροισμα`),
then converts the 4 fixed amount fields into a `amounts` list with Greek labels.
Returns a flat `list[dict]` of unified items.

#### `technical_extractor.py`

Calls the LLM backend, maps `projectCode` → `code`, passes `items` through as
`amounts` directly (they are already `[{label, amount}]` from the validator).
Returns the same flat `list[dict]` shape.

### `loaders/db_loader.py`

Two public functions:

```python
register_document(filename, doc_type, municipality, year, ada_code=None) → int
load_items(document_id, items)
```

`load_items` iterates the item list, inserts an `Item` row, then inserts one
`ItemAmount` row per entry in `item["amounts"]`.  Uses psycopg2 directly —
no ORM — to stay decoupled from Prisma's migration state.

### `discovery/diavgeia_client.py`

Uses the Diavgeia v2 REST API (`https://diavgeia.gov.gr/opendata/`) to:
1. Look up a municipality's UID from its Greek name
2. Search for decisions of type Β1, Β2 (budget) and Ε (technical program)
   published in the given year
3. Download the PDF attachment for each decision

Returns a list of `{"ada": ..., "doc_type": ..., "pdf_path": ...}` dicts.

---

## Database Schema

Managed by Prisma; the ETL writes via raw psycopg2.

```
Document
├── id          SERIAL PK
├── filename    TEXT
├── docType     ENUM (BUDGET | TECHNICAL_PROGRAM)
├── municipality TEXT
├── year        INT
├── adaCode     TEXT?          — Diavgeia decision identifier
└── importedAt  TIMESTAMP

Item
├── id          SERIAL PK
├── documentId  INT  → Document.id
├── code        TEXT           — KAE code or project code
├── description TEXT
└── parentCode  TEXT?          — null for TECHNICAL_PROGRAM items

ItemAmount
├── id      SERIAL PK
├── itemId  INT  → Item.id
├── label   TEXT           — e.g. "ΠΥ 2025", "Προϋπολογισμός"
└── amount  DECIMAL(15,2)
```

One schema serves both document types.  The web layer queries the same tables
regardless of `docType`; rendering differences (indent, chart) are handled at
the page level.

### Migrations

Two migrations in `web/prisma/migrations/`:

| Migration | What it does |
|---|---|
| `20260309142321_init` | Creates `Document`, `DocType` enum |
| `20260309200000_unified_schema` | Drops old 4-table model; creates `Item` + `ItemAmount` |

Apply with:
```bash
npx prisma migrate deploy   # non-interactive; safe for CI
```

---

## Web App (`web/`)

Built with Next.js 14 App Router, Prisma Client, Recharts.

### API Routes

#### `GET /api/documents`
Returns all documents ordered by `importedAt desc`.  Includes `_count.items`
for the row-count column in the document list.

#### `GET /api/items?documentId=N`
Returns `Item[]` with nested `amounts: ItemAmount[]`, ordered by `id`.

### Pages

#### `/` — Document List (`app/page.tsx`)
- Municipality filter via `?municipality=` query param (server-rendered `<form>`)
- Table with filename (link), type, municipality, year, item count, ADA link, import date
- All links go to `/document/[id]` regardless of `docType`

#### `/document/[id]` — Unified Detail (`app/document/[id]/page.tsx`)
- Fetches `Item[]` with `amounts` for the document
- Derives column headers dynamically from the distinct `label` values found in
  `ItemAmount` rows (so budget docs get 4 columns, technical docs get 2)
- **BUDGET rendering**: indent level derived from `code` at render time via
  `getLevel(code)` — no stored `level` field needed
  - `"00"` → level 0 (bold, grey background)
  - `"00-60"` → level 1 (bold)
  - `"00-603"` → level 2, `"00-6031"` → level 3, `"00-6031.0001"` → level 4
  - Pie chart (`BudgetChart`) of ΠΥ 2025 amounts, top 8 buckets by level-0/1 code
- **TECHNICAL_PROGRAM rendering**: flat list, no indent, no chart

#### `app/components/BudgetChart.tsx`
Recharts `PieChart` accepting `{name, value}[]`.  Client component.

---

## Environment Variables

Both `etl/.env` and `web/.env` need:
```
DATABASE_URL=postgresql://budget:budget@localhost:5432/municipal_budget
```

ETL only:
```
ANTHROPIC_API_KEY=sk-ant-...   # optional; activates Claude Haiku backend
OLLAMA_MODEL=qwen2.5:7b        # optional; default Ollama model
OLLAMA_HOST=http://localhost:11434  # optional
```

---

## Known Limitations (PoC)

- No pagination — all items fetched in one query
- No auth
- `test_pdfs/` PDFs are not committed (too large for git) — run ETL to populate DB
- `1_x.pdf` / `2_x.pdf` in `budget_past/` and `budget_plan/` are unrelated research
  PDFs — do not run ETL on them
- Prisma DLL (`query_engine-windows.dll.node`) is locked on Windows while `npm run dev`
  is running; kill the dev server before `npx prisma generate`
