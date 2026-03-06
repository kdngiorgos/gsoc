"""Extract structured data from Greek Municipal Technical Program PDFs.

Handles documents of type TECHNICAL_PROGRAM (Τεχνικό Πρόγραμμα).
These contain project listings with:
  - Section numbering (1.1, 1.2, ..., 2.1, ...)
  - Project codes (e.g. "25-7412.007", "30-7323.096")
  - Project descriptions (Greek text)
  - Budget reference codes (e.g. "..9762.05.049")
  - 5–8 monetary amount columns

Extraction strategy mirrors budget_extractor:
  1. pdfplumber (primary)
  2. camelot lattice / stream (fallback)
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional

import pdfplumber

from transformers.amount_parser import parse_amount

logger = logging.getLogger(__name__)

_PROJECT_CODE_RE = re.compile(r"^\d{2}-\d{4}\.\d{3}$")
_SECTION_RE = re.compile(r"^\d+\.\d+$")
_MIN_COLS = 3


def _looks_like_project_code(value: str) -> bool:
    return bool(_PROJECT_CODE_RE.match(value.strip()))


def _looks_like_section(value: str) -> bool:
    return bool(_SECTION_RE.match(value.strip()))


def _extract_tables_pdfplumber(pdf_path: Path) -> List[List[List[Optional[str]]]]:
    tables = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            page_tables = page.extract_tables()
            if page_tables:
                tables.extend(page_tables)
    return tables


def _extract_tables_camelot(pdf_path: Path) -> List[List[List[Optional[str]]]]:
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
                tables.append(t.df.values.tolist())
            if tables:
                logger.info("camelot (%s) found %d tables", flavor, len(tables))
                return tables
        except Exception as exc:
            logger.debug("camelot %s failed: %s", flavor, exc)
    return tables


def _infer_amount_column_labels(n_cols: int, first_data_col: int) -> List[str]:
    """Generate generic labels for amount columns when headers are absent."""
    generic = [
        "Προϋπολογισμός Μελέτης",
        "Εγκεκριμένη Πίστωση",
        "Πληρωμές έως 31/12",
        "Εκκρεμείς Υποχρεώσεις",
        "Υπόλοιπο Πίστωσης",
        "Νέα Πίστωση",
        "Σύνολο",
        "Παρατηρήσεις",
    ]
    labels = []
    for i in range(first_data_col, n_cols):
        idx = i - first_data_col
        labels.append(generic[idx] if idx < len(generic) else f"Ποσό_{idx + 1}")
    return labels


def extract_technical(pdf_path: Path) -> Dict:
    """Extract technical program data from a PDF file.

    Returns a dict with key:
      - "projects": list of project dicts, each containing:
          section, projectCode, description, budgetRef, items (label+amount pairs)
    """
    pdf_path = Path(pdf_path)
    logger.info("Extracting technical program from %s", pdf_path.name)

    all_tables = _extract_tables_pdfplumber(pdf_path)
    if not all_tables:
        logger.info("pdfplumber found no tables, trying camelot")
        all_tables = _extract_tables_camelot(pdf_path)

    if not all_tables:
        logger.warning("No tables found in %s", pdf_path.name)
        return {"projects": []}

    projects: List[Dict] = []

    for table in all_tables:
        if not table:
            continue

        # Detect header row to find amount column labels
        header_labels: List[str] = []
        data_start = 0
        first_amount_col = 3  # default: section, code, desc, [budget_ref], amounts...

        for row_idx, row in enumerate(table[:5]):
            # A header row will have mostly non-numeric strings
            non_empty = [c for c in row if c and c.strip()]
            if len(non_empty) >= 3 and not any(_looks_like_section(c) for c in non_empty):
                # Grab everything from col 3 onward as amount labels
                header_labels = [(c or "").strip() for c in row[first_amount_col:]]
                data_start = row_idx + 1
                break

        for row in table[data_start:]:
            if not row or len(row) < _MIN_COLS:
                continue

            cells = [(c or "").strip() for c in row]

            # Identify section number (e.g. "1.1")
            section = ""
            project_code = ""
            description = ""
            budget_ref = ""
            amount_start_col = first_amount_col

            # Try to locate section and project code in first few columns
            for i, cell in enumerate(cells[:4]):
                if _looks_like_section(cell) and not section:
                    section = cell
                elif _looks_like_project_code(cell) and not project_code:
                    project_code = cell
                elif cell.startswith("..") and not budget_ref:
                    budget_ref = cell
                elif cell and not description and not _looks_like_section(cell) \
                        and not _looks_like_project_code(cell):
                    # Likely description
                    description = cell

            if not project_code:
                continue

            # Amount columns
            amount_cells = cells[amount_start_col:]
            if not header_labels:
                labels = _infer_amount_column_labels(len(cells), amount_start_col)
            else:
                labels = header_labels

            items = []
            for label, raw_val in zip(labels, amount_cells):
                amount = parse_amount(raw_val)
                if amount is not None:
                    items.append({"label": label, "amount": amount})

            projects.append({
                "section": section,
                "projectCode": project_code,
                "description": description,
                "budgetRef": budget_ref or None,
                "items": items,
            })

    logger.info("Extracted %d projects from %s", len(projects), pdf_path.name)
    return {"projects": projects}
