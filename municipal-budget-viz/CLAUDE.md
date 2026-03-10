# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## Project Overview

PoC for a Greek Municipal Budget and Technical Program Visualization Tool (GSoC / OpenCouncil).
Parses complex Greek PDF budget documents, stores structured data in PostgreSQL, and displays
it via a minimal Next.js frontend.

Two PDF document types are processed:
- **BUDGET** (`ΔΑΠΑΝΕΣ`, `Τεύχος Προϋπολογισμού`): hierarchical KAE expense codes with
  year-comparison amounts (ΠΥ 2024, Αναμορφωμένος, ΠΥ 2025, Διαφορά)
- **TECHNICAL_PROGRAM** (`Τεχνικό Πρόγραμμα`): infrastructure project listings with
  Προϋπολογισμός + Ποσό columns

Test PDFs live in `../test_pdfs/` (relative to `municipal-budget-viz/`):
- `technical_acharne.pdf` — TECHNICAL_PROGRAM
- `budget_palaio_faliro.pdf` — BUDGET
- `budget_rodos.pdf` — BUDGET

## Commands

### ETL (Python) — run from `etl/`
```bash
cd etl/
pip install -r requirements.txt
cp .env.example .env          # DATABASE_URL already correct for Docker

# Manual mode
python pipeline.py --input ../../test_pdfs/technical_acharne.pdf --type technical
python pipeline.py --input ../../test_pdfs/budget_palaio_faliro.pdf --type budget
python pipeline.py --input ../../test_pdfs/budget_rodos.pdf --type budget

# Diavgeia discovery mode (auto-downloads PDFs for a municipality)
python pipeline.py --municipality "Αχαρνές" --year 2025

pytest tests/    # 55+ passing unit tests
```

### Web (Next.js) — run from `web/`
```bash
cd web/
npm install
cp .env.example .env          # DATABASE_URL already correct for Docker
npx prisma migrate deploy     # apply all migrations (non-interactive, safe for CI)
npx prisma generate           # regenerate Prisma client
npm run dev                   # http://localhost:3000
npm run build                 # TypeScript check + production build
```

### Docker
```bash
docker compose up -d postgres             # DB only
docker compose up                         # full stack (postgres + web)
```

### DB inspection
```bash
docker exec municipal-budget-viz-postgres-1 psql -U budget -d municipal_budget \
  -c 'SELECT COUNT(*) FROM "Item"; SELECT COUNT(*) FROM "ItemAmount";'
```

### Windows convenience scripts (from `municipal-budget-viz/`)
```powershell
.\run.ps1    # start Docker + Next.js dev server
.\stop.ps1   # stop everything
```

## Architecture

```
PDFs  →  etl/pipeline.py  →  PostgreSQL  ←  web/prisma/schema.prisma
                                         ↑
                              web/app/api/   (Next.js API routes)
                                         ↑
                              web/app/        (Next.js pages)
```

### ETL Pipeline (`etl/`)

| File | Role |
|---|---|
| `pipeline.py` | CLI orchestrator; auto-detects doc type from filename keywords |
| `extractors/budget_extractor.py` | pdfplumber text → LLM → flat `list[dict]` |
| `extractors/technical_extractor.py` | pdfplumber text → LLM → flat `list[dict]` |
| `extractors/claude_extractor.py` | Claude Haiku backend (used when `ANTHROPIC_API_KEY` is set) |
| `extractors/ollama_extractor.py` | Ollama backend (local fallback); also defines prompts & validators |
| `extractors/text_extractor.py` | pdfplumber page-text utility |
| `transformers/amount_parser.py` | Parses European number format (`"1.661.761,40"` → `Decimal`) |
| `transformers/kae_parser.py` | Legacy — not called by current pipeline |
| `loaders/db_loader.py` | psycopg2 loader; single `load_items()` for both doc types |
| `discovery/diavgeia_client.py` | Queries Diavgeia API; downloads PDFs for any municipality |

**Extraction flow for both doc types:**
```
PDF → pdfplumber.extract_text() (per page)
    → LLM prompt (Claude Haiku or Ollama) → JSON
    → _validate_budget_item() / _validate_project()
    → budget_extractor / technical_extractor  (normalise to unified shape)
    → load_items() → PostgreSQL
```

**LLM backend selection** (in `budget_extractor.py` and `technical_extractor.py`):
- If `ANTHROPIC_API_KEY` is set → `claude_extractor.py` (Claude Haiku)
- Otherwise → `ollama_extractor.py` (local Ollama, default model `qwen2.5:7b`)

### Unified Data Shape (ETL output)

Both extractors return the same flat list — no special-casing in the loader:

```python
[
  {
    "code":        "00-6031",        # KAE code (budget) or project code (technical)
    "description": "...",
    "parentCode":  "00-603",         # derived from code structure; None for technical
    "amounts": [
      {"label": "ΠΥ 2025", "amount": Decimal("1234.56")},
      ...
    ],
  },
  ...
]
```

### KAE Code Hierarchy (BUDGET only)

```
Level 0: "00"           — section
Level 1: "00-60"        — group        (parent: "00")
Level 2: "00-603"       — article      (parent: "00-60")
Level 3: "00-6031"      — sub-item     (parent: "00-603")
Level 4: "00-6031.0001" — detail       (parent: "00-6031")
```

`parentCode` is derived by code truncation (no separate lookup table).

### Database Schema (`web/prisma/schema.prisma`)

```
Document
  id, filename, docType (BUDGET | TECHNICAL_PROGRAM), municipality, year, adaCode, importedAt
  └─ Item[]
       id, documentId, code, description, parentCode
       └─ ItemAmount[]
            id, itemId, label, amount (Decimal 15,2)
```

One schema serves both document types. `parentCode` is `null` for TECHNICAL_PROGRAM items.

### Web (`web/`)

| Route | Description |
|---|---|
| `GET /api/documents` | List all documents with `_count.items` |
| `GET /api/items?documentId=N` | All `Item` rows (with nested `amounts`) for a document |
| `/` | Document list with municipality filter |
| `/document/[id]` | Unified detail page for BUDGET and TECHNICAL_PROGRAM |

**Detail page behaviour** (`web/app/document/[id]/page.tsx`):
- Columns are built dynamically from the distinct `label` values in `ItemAmount` rows
- BUDGET: KAE indent derived from `code` structure at render time; pie chart of ΠΥ 2025 by top-level bucket
- TECHNICAL: flat list, no indent

## Key Technical Notes

- Greek PDFs use European number format: `.` = thousands separator, `,` = decimal
- ETL connects via psycopg2 directly — Prisma is web-only
- `DATABASE_URL` must be set in both `etl/.env` and `web/.env`
- `docker-compose.yml` has an obsolete `version:` key — harmless warning
- Prisma DLL (`query_engine-windows.dll.node`) is locked while `npm run dev` is running;
  kill the dev server before running `npx prisma generate`
- Use `prisma migrate deploy` (not `migrate dev`) for non-interactive migration

## User Preferences

- Do NOT write application code without explicit architecture approval
- NEVER add `Co-Authored-By` lines to git commits
- Keep `run.ps1` and `run.sh` in sync — changes to one must be reflected in the other
