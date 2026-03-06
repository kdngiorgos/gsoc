# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PoC for a Greek Municipal Budget and Technical Program Visualization Tool (GSoC / OpenCouncil).
Parses complex Greek PDF budget documents, stores structured data in PostgreSQL, and displays it via a minimal Next.js frontend.

Two PDF document types are processed:
- **BUDGET** (`ΔΑΠΑΝΕΣ`, `Τεύχος Προϋπολογισμού`): hierarchical KAE expense/income codes with year-comparison amounts
- **TECHNICAL_PROGRAM** (`Τεχνικό Πρόγραμμα`): infrastructure project listings with 5–8 budget amount columns

PDF source folders: `../budget_past/` and `../budget_plan/` (relative to project root, outside this directory).

## Commands

### ETL (Python) — run from `etl/`
```bash
cd etl/
pip install -r requirements.txt
cp .env.example .env          # then fill in DATABASE_URL

python pipeline.py --input ../budget_past/ --type auto
python pipeline.py --input ../budget_plan/ --type auto
python pipeline.py --input path/to/single.pdf --type budget
python pipeline.py --input path/to/single.pdf --type technical

pytest tests/                              # all tests
pytest tests/test_kae_parser.py -v         # single test file
```

### Web (Next.js) — run from `web/`
```bash
cd web/
npm install
cp .env.example .env          # then fill in DATABASE_URL
npx prisma migrate dev --name init
npx prisma generate
npm run dev                   # http://localhost:3000
npm run build && npm start    # production
```

### Docker
```bash
docker compose up -d postgres             # DB only
docker compose up                         # full stack
```

### DB inspection
```bash
psql postgresql://budget:budget@localhost:5432/municipal_budget
SELECT COUNT(*) FROM "BudgetItem";
SELECT COUNT(*) FROM "TechnicalProject";
```

## Architecture

```
PDFs → etl/pipeline.py → PostgreSQL ← web/prisma/schema.prisma
                                    ↑
                         web/app/api/ (Next.js API routes)
                                    ↑
                         web/app/    (Next.js pages — skeleton)
```

### ETL Pipeline (`etl/`)
- `pipeline.py` — CLI orchestrator; auto-detects doc type from filename keywords
- `extractors/budget_extractor.py` — pdfplumber primary, camelot fallback; detects KAE codes
- `extractors/technical_extractor.py` — same strategy; detects project codes (`XX-YYYY.ZZZ`)
- `transformers/kae_parser.py` — reconstructs parent-child tree from code structure alone
- `transformers/amount_parser.py` — parses European number format (`"1.661.761,40"` → `Decimal`)
- `loaders/db_loader.py` — psycopg2 upserts; inserts categories before items (order matters for FK)

### KAE Code Hierarchy (Format A)
- Level 0: `"00"` — section
- Level 1: `"00-60"` — group
- Level 2: `"00-603"` — article
- Level 3: `"00-6031"` — sub-item
- Level 4: `"00-6031.0001"` — detail

Parent derived by code truncation (no separate lookup needed).

### Database (`web/prisma/schema.prisma`)
- `Document` → `BudgetItem` → `BudgetCategory` (self-referential tree via `parentId`)
- `Document` → `TechnicalProject` → `TechnicalProjectItem` (one row per amount column)
- All monetary columns are `Decimal(15,2)`

### Web (`web/`)
- Three pages: `/` (document list), `/budget/[id]` (indented KAE tree table), `/technical/[id]` (project table)
- Three API routes under `app/api/` returning Prisma JSON
- No auth, no pagination — PoC only

## Key Technical Notes

- Greek PDFs use European number format: `.` = thousands separator, `,` = decimal
- `pdfplumber` works best for text-layer PDFs; `camelot` is the fallback for bordered/stream tables
- `camelot-py[cv]` requires `ghostscript` and `opencv` to be installed on the system
- The ETL connects directly via psycopg2; Prisma is used only by the web layer
- `DATABASE_URL` must be set in both `etl/.env` and `web/.env`
