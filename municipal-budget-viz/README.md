# Municipal Budget Visualization Tool

A PoC tool for extracting, storing, and visualising Greek municipal budget
and technical-program PDFs published on Diavgeia.

Built for the OpenCouncil GSoC project.

---

## What it does

- Downloads budget PDFs from [Diavgeia](https://diavgeia.gov.gr) for any Greek municipality
- Parses two document types:
  - **BUDGET** (`ΔΑΠΑΝΕΣ`) — hierarchical KAE expense codes with year-comparison amounts
  - **TECHNICAL_PROGRAM** (`Τεχνικό Πρόγραμμα`) — infrastructure project listings
- Stores structured data in PostgreSQL
- Displays documents via a Next.js web app with:
  - Keyword search across all items
  - KAE hierarchy view with indentation levels
  - Pie chart of top spending buckets
  - Year-over-year bar chart (ΠΥ 2024 vs ΠΥ 2025)
  - Links to source decisions on Diavgeia

---

## Requirements

- Docker Desktop
- Node.js 18+
- Python 3.11+

---

## Quick start

### 1. Start PostgreSQL

```bash
cd municipal-budget-viz
docker compose up -d postgres
```

### 2. Set up the web app

```bash
cd web
cp .env.example .env
npm install
npx prisma migrate deploy
npx prisma generate
npm run dev         # http://localhost:3000
```

### 3. Set up the ETL

```bash
cd etl
cp .env.example .env
pip install -r requirements.txt
```

Set `ANTHROPIC_API_KEY` in `etl/.env` to use Claude Haiku for extraction.
Without it, the pipeline falls back to a local Ollama model (`qwen2.5:7b`).

### 4. Import documents

**Option A — Diavgeia discovery (recommended)**

```bash
cd etl
python pipeline.py --municipality "Αχαρνές" --year 2025
```

This automatically finds and downloads the relevant PDFs from Diavgeia.

**Option B — Local PDF files**

```bash
cd etl
python pipeline.py --input ../../test_pdfs/budget_palaio_faliro.pdf --type budget --manual-municipality "Παλαιό Φάληρο"
python pipeline.py --input ../../test_pdfs/technical_acharne.pdf --type technical --manual-municipality "Αχαρνές"
```

Supported `--type` values: `budget`, `technical`, `auto` (default — detects from filename).

---

## Windows convenience scripts

From `municipal-budget-viz/`:

```powershell
.\run.ps1    # start Docker + Next.js dev server
.\stop.ps1   # stop everything
```

---

## Project structure

```
municipal-budget-viz/
├── docker-compose.yml
├── run.ps1 / run.sh / stop.ps1 / stop.sh
├── etl/
│   ├── pipeline.py               # CLI entry point
│   ├── extractors/
│   │   ├── budget_extractor.py   # pdfplumber + LLM for BUDGET docs
│   │   ├── technical_extractor.py
│   │   ├── claude_extractor.py   # Claude Haiku backend
│   │   └── ollama_extractor.py   # Ollama backend (local fallback)
│   ├── loaders/
│   │   └── db_loader.py          # psycopg2 loader (duplicate-safe)
│   ├── discovery/
│   │   └── diavgeia_client.py    # Diavgeia REST API client
│   └── tests/                    # 55+ unit tests (pytest)
└── web/
    ├── prisma/schema.prisma      # DB schema (Document → Item → ItemAmount)
    ├── app/
    │   ├── page.tsx              # Document list + keyword search
    │   ├── document/[id]/page.tsx
    │   ├── components/
    │   │   ├── BudgetChart.tsx   # Pie chart
    │   │   └── YearChart.tsx     # Year-over-year bar chart
    │   └── api/
    │       ├── documents/route.ts
    │       ├── items/route.ts
    │       └── search/route.ts   # GET /api/search?q=...
    └── lib/db.ts                 # Prisma client singleton
```

---

## Database schema

```
Document
  id, filename, docType (BUDGET | TECHNICAL_PROGRAM),
  municipality, year, adaCode, importedAt
  └─ Item[]
       id, documentId, code, description, parentCode
       └─ ItemAmount[]
            id, itemId, label, amount (Decimal 15,2)
```

KAE hierarchy is derived from the `code` field at read time — no separate
hierarchy table is needed.

---

## Running the tests

```bash
cd etl
pytest tests/ -v
```

---

## Known limitations

- Scanned PDFs (image-only) are not supported — pdfplumber cannot OCR
- Cross-municipality comparison view is not yet implemented
- Incremental updates re-import from scratch per document (duplicate detection
  prevents double-counting on re-runs)
