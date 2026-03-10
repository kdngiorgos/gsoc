"""Tier-2 text-mode extraction for Greek municipal PDFs.

Falls back to page.extract_text() and regex parsing when pdfplumber
table detection finds nothing. No new dependencies beyond pdfplumber.
"""

from __future__ import annotations

import logging
import re
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional

import pdfplumber

from transformers.amount_parser import parse_amount

logger = logging.getLogger(__name__)

# KAE code at the very start of a line (with trailing whitespace)
_KAE_LINE_RE = re.compile(
    r"^(\d{2}(?:-\d{2,4}(?:\.\d{4})?)?|\d{4}(?:\.\d{5})?)\s+"
)

# Project code pattern anywhere on a line
_PROJECT_CODE_RE = re.compile(r"(?<!\d)(\d{2}-\d{4}\.\d{3})(?!\d)")

# Section number at start of line (e.g. "1.1")
_SECTION_RE = re.compile(r"^(\d+\.\d+)\s+")

# European-format monetary amount
_AMOUNT_RE = re.compile(r"\b\d{1,3}(?:\.\d{3})*,\d{2}\b")

# Budget reference code starting with ".."
_BUDGET_REF_RE = re.compile(r"\.\.\S+")


def _parse_budget_lines(lines: List[str]) -> List[Dict]:
    """Parse KAE budget lines into raw item dicts.

    Returns one dict per KAE-coded line (subtotals not filtered here —
    budget_extractor._classify_and_route handles that). Each dict has:
      code, description, amount2024, amountMidYear, amount2025, amountVariance
    """
    items: List[Dict] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue

        m = _KAE_LINE_RE.match(line)
        if not m:
            continue

        code = m.group(1)
        rest = line[m.end():]

        # Description = text before the first amount
        first_amt = _AMOUNT_RE.search(rest)
        description = rest[:first_amt.start()].strip() if first_amt else rest.strip()

        # Parse up to 4 amount slots
        amounts_raw = _AMOUNT_RE.findall(rest)
        parsed = [parse_amount(a) for a in amounts_raw]

        items.append({
            "code": code,
            "description": description,
            "amount2024":    parsed[0] if len(parsed) > 0 else None,
            "amountMidYear": parsed[1] if len(parsed) > 1 else None,
            "amount2025":    parsed[2] if len(parsed) > 2 else None,
            "amountVariance": parsed[3] if len(parsed) > 3 else None,
        })

    return items


def _parse_technical_lines(lines: List[str]) -> List[Dict]:
    """Parse technical-program lines into raw project dicts.

    Returns one dict per project code found, with multi-line descriptions
    buffered between project codes. Format matches load_technical() input:
      section, projectCode, description, budgetRef, items (label+amount pairs)
    """
    _GENERIC_LABELS = [
        "Προϋπολογισμός Μελέτης",
        "Εγκεκριμένη Πίστωση",
        "Πληρωμές έως 31/12",
        "Εκκρεμείς Υποχρεώσεις",
        "Υπόλοιπο Πίστωσης",
        "Νέα Πίστωση",
        "Σύνολο",
        "Παρατηρήσεις",
    ]

    projects: List[Dict] = []
    current: Optional[Dict] = None
    desc_buffer: List[str] = []

    def _flush():
        if current is not None:
            if desc_buffer:
                extra = " ".join(desc_buffer).strip()
                if current["description"]:
                    current["description"] = current["description"] + " " + extra
                else:
                    current["description"] = extra
            projects.append(current)

    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            continue

        code_m = _PROJECT_CODE_RE.search(line_stripped)
        if code_m:
            _flush()
            desc_buffer = []

            project_code = code_m.group(1)
            pre = line_stripped[: code_m.start()].strip()
            rest = line_stripped[code_m.end() :].strip()

            # Section (e.g. "1.1") before the project code
            sec_m = _SECTION_RE.match(pre + " ")
            section = sec_m.group(1) if sec_m else ""

            # Budget ref (e.g. "..9762.05.049")
            budget_ref: Optional[str] = None
            br_m = _BUDGET_REF_RE.search(rest)
            if br_m:
                budget_ref = br_m.group(0)
                rest = (rest[: br_m.start()] + rest[br_m.end() :]).strip()

            # Description = text before first amount
            first_amt = _AMOUNT_RE.search(rest)
            inline_desc = rest[: first_amt.start()].strip() if first_amt else rest.strip()

            # Amount items
            amounts_raw = _AMOUNT_RE.findall(rest)
            amount_items = []
            for i, raw in enumerate(amounts_raw):
                amount = parse_amount(raw)
                if amount is not None:
                    label = _GENERIC_LABELS[i] if i < len(_GENERIC_LABELS) else f"Ποσό_{i + 1}"
                    amount_items.append({"label": label, "amount": amount})

            current = {
                "section": section,
                "projectCode": project_code,
                "description": inline_desc,
                "budgetRef": budget_ref,
                "items": amount_items,
            }

        elif current is not None:
            # Buffer lines between project codes as potential description continuation.
            # Skip pure-amount lines and obvious summary lines.
            if not _AMOUNT_RE.search(line_stripped):
                desc_buffer.append(line_stripped)

    _flush()
    return projects


def extract_budget_text(pdf_path: Path) -> List[Dict]:
    """Tier-2 budget extraction: parse raw page text with regex."""
    pdf_path = Path(pdf_path)
    lines: List[str] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            lines.extend((page.extract_text() or "").splitlines())

    items = _parse_budget_lines(lines)
    logger.info("text_extractor (budget): %d raw rows from %s", len(items), pdf_path.name)
    return items


def extract_technical_text(pdf_path: Path) -> List[Dict]:
    """Tier-2 technical extraction: parse raw page text with regex."""
    pdf_path = Path(pdf_path)
    lines: List[str] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            lines.extend((page.extract_text() or "").splitlines())

    projects = _parse_technical_lines(lines)
    logger.info("text_extractor (technical): %d projects from %s", len(projects), pdf_path.name)
    return projects
