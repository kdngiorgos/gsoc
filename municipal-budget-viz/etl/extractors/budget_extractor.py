"""Extract structured data from Greek municipal budget PDFs.

Handles documents of type BUDGET (Προϋπολογισμός / ΔΑΠΑΝΕΣ).
These contain tables with KAE codes, descriptions, and multiple
year-comparison amount columns.

Extraction strategy:
  1. Try pdfplumber page.extract_tables() (good for text-layer PDFs)
  2. Fall back to camelot lattice mode (bordered tables)
  3. Fall back to camelot stream mode (whitespace-aligned columns)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional

import pdfplumber

from transformers.amount_parser import parse_amount
from transformers.kae_parser import KaeNode, build_category_tree

logger = logging.getLogger(__name__)


# Heuristic column-name patterns (matched case-insensitively)
_COL_CODE        = ("κωδικός", "κωδ", "code")
_COL_DESC        = ("περιγραφή", "τίτλος", "description")
_COL_AMT_2024    = ("2024", "διαμορφωθέν", "εγκριθέν")
_COL_MID_YEAR    = ("30/9", "31/8", "μέχρι")
_COL_AMT_2025    = ("2025", "προτεινόμενο", "εγκριθέν 2025")
_COL_VARIANCE    = ("διαφορά", "μεταβολή")

# Minimum columns a row must have to be considered a data row
_MIN_COLS = 3


def _match_header(cell: Optional[str], patterns: tuple) -> bool:
    if not cell:
        return False
    lower = cell.lower().strip()
    return any(p in lower for p in patterns)


def _detect_column_map(header_row: List[Optional[str]]) -> Dict[str, int]:
    """Map semantic column names to their indices from a header row."""
    col_map: Dict[str, int] = {}
    for i, cell in enumerate(header_row):
        if _match_header(cell, _COL_CODE):
            col_map.setdefault("code", i)
        elif _match_header(cell, _COL_DESC):
            col_map.setdefault("description", i)
        elif _match_header(cell, _COL_AMT_2025):
            col_map.setdefault("amount2025", i)
        elif _match_header(cell, _COL_AMT_2024):
            col_map.setdefault("amount2024", i)
        elif _match_header(cell, _COL_MID_YEAR):
            col_map.setdefault("amountMidYear", i)
        elif _match_header(cell, _COL_VARIANCE):
            col_map.setdefault("amountVariance", i)
    return col_map


def _looks_like_kae(value: str) -> bool:
    """Return True if value resembles a KAE budget code."""
    v = value.strip()
    # e.g. "00", "00-60", "00-6031", "00-6031.0001", "0111", "0111.00000"
    import re
    return bool(
        re.match(r"^\d{2}(-\d{2,4}(\.\d{4})?)?$", v)
        or re.match(r"^\d{4}(\.\d{5})?$", v)
    )


def _extract_tables_pdfplumber(pdf_path: Path) -> List[List[List[Optional[str]]]]:
    """Return list of tables (each table is list of rows, each row is list of cells)."""
    tables = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            page_tables = page.extract_tables()
            if page_tables:
                tables.extend(page_tables)
    return tables


def _extract_tables_camelot(pdf_path: Path) -> List[List[List[Optional[str]]]]:
    """Fallback table extraction using camelot."""
    try:
        import camelot
    except ImportError:
        logger.warning("camelot-py not installed; skipping fallback extraction")
        return []

    tables = []
    for flavor in ("lattice", "stream"):
        try:
            result = camelot.read_pdf(str(pdf_path), pages="all", flavor=flavor)
            for t in result:
                rows = t.df.values.tolist()
                tables.append(rows)
            if tables:
                logger.info("camelot (%s) found %d tables", flavor, len(tables))
                return tables
        except Exception as exc:
            logger.debug("camelot %s failed: %s", flavor, exc)
    return tables


def extract_budget(pdf_path: Path) -> Dict:
    """Extract budget data from a PDF file.

    Returns a dict with keys:
      - "categories": list of KaeNode
      - "items": list of raw row dicts ready for DB insertion
    """
    pdf_path = Path(pdf_path)
    logger.info("Extracting budget from %s", pdf_path.name)

    all_tables = _extract_tables_pdfplumber(pdf_path)
    if not all_tables:
        logger.info("pdfplumber found no tables, trying camelot")
        all_tables = _extract_tables_camelot(pdf_path)

    if not all_tables:
        logger.warning("No tables found in %s", pdf_path.name)
        return {"categories": [], "items": []}

    raw_category_rows: List[Dict[str, str]] = []
    raw_item_rows: List[Dict] = []

    for table in all_tables:
        if not table:
            continue

        # Try to detect header row (first row that contains recognizable column labels)
        col_map: Dict[str, int] = {}
        data_start = 0

        for row_idx, row in enumerate(table[:5]):  # header is usually in first 5 rows
            candidate = _detect_column_map(row)
            if "code" in candidate or "description" in candidate:
                col_map = candidate
                data_start = row_idx + 1
                break

        if not col_map:
            # Heuristic: assume first col = code, second = description, rest = amounts
            col_map = {"code": 0, "description": 1}
            amount_labels = ["amount2024", "amountMidYear", "amount2025", "amountVariance"]
            for i, label in enumerate(amount_labels):
                if 2 + i < (len(table[0]) if table else 0):
                    col_map[label] = 2 + i
            data_start = 0

        code_col = col_map.get("code", 0)
        desc_col = col_map.get("description", 1)

        for row in table[data_start:]:
            if not row or len(row) < _MIN_COLS:
                continue
            code_val = (row[code_col] or "").strip() if code_col < len(row) else ""
            desc_val = (row[desc_col] or "").strip() if desc_col < len(row) else ""

            if not code_val or not _looks_like_kae(code_val):
                continue

            raw_category_rows.append({"code": code_val, "description": desc_val})

            item: Dict = {
                "code": code_val,
                "description": desc_val,
                "amount2024": None,
                "amountMidYear": None,
                "amount2025": None,
                "amountVariance": None,
            }
            for field in ("amount2024", "amountMidYear", "amount2025", "amountVariance"):
                col_idx = col_map.get(field)
                if col_idx is not None and col_idx < len(row):
                    item[field] = parse_amount(row[col_idx] or "")
            raw_item_rows.append(item)

    categories = build_category_tree(raw_category_rows)
    logger.info(
        "Extracted %d categories, %d items from %s",
        len(categories), len(raw_item_rows), pdf_path.name,
    )
    return {"categories": categories, "items": raw_item_rows}
