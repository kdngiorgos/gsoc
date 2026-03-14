"""Ollama-based extraction for Greek municipal budget and technical program PDFs.

Uses pdfplumber.extract_text() per page (plain text, not tables) and feeds
each page to a local Ollama model.

The Ollama `format="json"` parameter enforces valid JSON output at the grammar
level — no post-hoc markdown stripping needed.
"""

from __future__ import annotations

import json
import logging
import os
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Dict, List, Optional

import pdfplumber

logger = logging.getLogger(__name__)

OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")
OLLAMA_HOST  = os.environ.get("OLLAMA_HOST",  "http://localhost:11434")

_BUDGET_PROMPT = """Extract all budget line items from this Greek municipal budget document text.

Return a JSON object: {{"items": [...]}}
Each item must have these fields:
  "code"          : KAE budget code string (e.g. "00", "00-60", "00-6031.0001")
  "description"   : Greek description string
  "amount2024"    : number or null  (previous year amount)
  "amountMidYear" : number or null  (mid-year amount)
  "amount2025"    : number or null  (current year amount)
  "amountVariance": number or null  (difference/variance)

Important rules:
- Greek numbers use dot as thousands separator and comma as decimal: "1.234,56" means 1234.56
- Skip rows that are totals or subtotals (containing: σύνολο, άθροισμα, σύνολα, ΣΥΝΟΛΟ)
- Include only rows that have a valid KAE code (format like "00", "00-60", "00-6031", "00-6031.0001")
- Return ONLY the JSON object, no other text, no markdown

TEXT:
{text}
"""

_TECHNICAL_PROMPT = """Extract all infrastructure project entries from this Greek municipal technical program text.

Return a JSON object: {{"projects": [...]}}
Each project must have these fields:
  "section"     : section number string (e.g. "1.1", "2.3") or ""
  "projectCode" : project code string (e.g. "25-7412.007", "30-7321.00018")
  "description" : Greek description string
  "budgetRef"   : budget reference string (KA code starting with digits-digits) or null
  "items"       : list of {{"label": string, "amount": number}} for MONETARY columns only

MANDATORY column label rules — always use EXACTLY these two Greek labels:
  "Προϋπολογισμός" — the total approved budget for the project
      Maps from: "Έγκριση", "Προϋπ.", "Συνολικός Π/Υ", "Προϋπολογισμός Έγκρισης", any total-budget column
  "Ποσό"           — the amount allocated for the current year
      Maps from: "Ποσό Έτους", "Ποσό για το 2025", "Ποσό 2025", "Ποσό 2024", any year-amount column

Other rules:
- Greek numbers use dot as thousands separator and comma as decimal: "1.234,56" means 1234.56
- Project codes follow pattern: two digits, dash, four digits, dot, digits (e.g. "25-7412.007")
- "items" must contain ONLY columns whose values are numbers (amounts in €)
- DO NOT include "Πηγή χρηματοδότησης" (funding source) in items — it is text, not a number
- DO NOT use English labels — always use the exact Greek canonical labels above
- If a column cannot be mapped to either canonical label, omit it from items
- Return ONLY the JSON object, no other text, no markdown

TEXT:
{text}
"""


def _get_client():
    """Create and return an Ollama client."""
    import ollama
    return ollama.Client(host=OLLAMA_HOST)


def _to_decimal(value) -> Optional[Decimal]:
    """Convert a value to Decimal, handling Greek number format and None.

    European format strings (containing a comma as decimal separator, e.g.
    "1.234,56") have their thousands dots stripped and decimal comma replaced.
    Standard floats/ints from JSON output are used directly without conversion.
    """
    if value is None:
        return None
    if isinstance(value, (int, float, Decimal)):
        try:
            return Decimal(repr(value)) if isinstance(value, float) else Decimal(value)
        except InvalidOperation:
            return None
    s = str(value).strip()
    if not s or s in ("-", "—", ""):
        return None
    if "," in s:
        # European format: "1.234,56" → "1234.56"
        s = s.replace(".", "").replace(",", ".")
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def _read_pages(pdf_path: Path, max_pages: Optional[int] = None) -> List[str]:
    """Extract plain text from PDF, returning one string per non-blank page."""
    pages_text = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        pages = pdf.pages[:max_pages] if max_pages is not None else pdf.pages
        for page in pages:
            text = page.extract_text()
            if text and text.strip():
                pages_text.append(text)
    return pages_text


def _call_ollama(client, prompt_template: str, text: str) -> Optional[Dict]:
    """Call Ollama with the given prompt template and text chunk.

    Returns parsed JSON dict or None on failure.
    """
    prompt = prompt_template.format(text=text)
    try:
        response = client.chat(
            model=OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}],
            format="json",
            options={"temperature": 0},
        )
        content = response.message.content
        return json.loads(content)
    except Exception as exc:
        logger.error("Ollama call failed: %s", exc)
        return None


def _validate_budget_item(obj: Dict) -> Optional[Dict]:
    """Validate and normalise a raw budget item dict from the LLM.

    Returns a normalised dict or None if the item is invalid.
    """
    code = (obj.get("code") or "").strip()
    if not code:
        return None

    description = (obj.get("description") or "").strip()

    return {
        "code": code,
        "description": description,
        "amount2024":    _to_decimal(obj.get("amount2024")),
        "amountMidYear": _to_decimal(obj.get("amountMidYear")),
        "amount2025":    _to_decimal(obj.get("amount2025")),
        "amountVariance": _to_decimal(obj.get("amountVariance")),
    }


def _validate_project(obj: Dict) -> Optional[Dict]:
    """Validate and normalise a raw project dict from the LLM.

    Returns a normalised dict or None if the project is invalid.
    """
    code = (obj.get("projectCode") or "").strip()
    if not code:
        return None

    raw_items = obj.get("items") or []
    items = []
    for it in raw_items:
        if not isinstance(it, dict):
            continue
        label = (it.get("label") or "").strip()
        amount = _to_decimal(it.get("amount"))
        if amount is not None and label:
            items.append({"label": label, "amount": amount})

    return {
        "section":     (obj.get("section") or "").strip(),
        "projectCode": code,
        "description": (obj.get("description") or "").strip(),
        "budgetRef":   (obj.get("budgetRef") or None),
        "items":       items,
    }


def extract_budget_ollama(pdf_path: Path, max_pages: Optional[int] = None) -> List[Dict]:
    """Extract budget items from a PDF using Ollama.

    Returns a flat list of normalised item dicts.
    Raises RuntimeError if Ollama is not reachable.
    """
    pdf_path = Path(pdf_path)
    logger.info("Ollama budget extraction: model=%s file=%s", OLLAMA_MODEL, pdf_path.name)

    try:
        client = _get_client()
        client.list()
    except Exception as exc:
        raise RuntimeError(
            f"Ollama is not reachable at {OLLAMA_HOST}. "
            f"Start it with: ollama serve  (error: {exc})"
        ) from exc

    pages = _read_pages(pdf_path, max_pages=max_pages)
    logger.info("  %d pages to process", len(pages))

    all_items: List[Dict] = []
    for idx, page_text in enumerate(pages, 1):
        result = _call_ollama(client, _BUDGET_PROMPT, page_text)
        if result is None:
            logger.warning("  page %d/%d: Ollama returned no result", idx, len(pages))
            continue

        raw_items = result.get("items") or []
        page_valid = 0
        for obj in raw_items:
            if not isinstance(obj, dict):
                continue
            item = _validate_budget_item(obj)
            if item is not None:
                all_items.append(item)
                page_valid += 1

        logger.info("  page %d/%d: %d valid items", idx, len(pages), page_valid)

    logger.info("Ollama budget extraction complete: %d total items from %s",
                len(all_items), pdf_path.name)
    return all_items


def extract_technical_ollama(pdf_path: Path, max_pages: Optional[int] = None) -> List[Dict]:
    """Extract technical projects from a PDF using Ollama.

    Returns a flat list of normalised project dicts.
    Raises RuntimeError if Ollama is not reachable.
    """
    pdf_path = Path(pdf_path)
    logger.info("Ollama technical extraction: model=%s file=%s", OLLAMA_MODEL, pdf_path.name)

    try:
        client = _get_client()
        client.list()
    except Exception as exc:
        raise RuntimeError(
            f"Ollama is not reachable at {OLLAMA_HOST}. "
            f"Start it with: ollama serve  (error: {exc})"
        ) from exc

    pages = _read_pages(pdf_path, max_pages=max_pages)
    logger.info("  %d pages to process", len(pages))

    all_projects: List[Dict] = []
    for idx, page_text in enumerate(pages, 1):
        result = _call_ollama(client, _TECHNICAL_PROMPT, page_text)
        if result is None:
            logger.warning("  page %d/%d: Ollama returned no result", idx, len(pages))
            continue

        raw_projects = result.get("projects") or []
        page_valid = 0
        for obj in raw_projects:
            if not isinstance(obj, dict):
                continue
            project = _validate_project(obj)
            if project is not None:
                all_projects.append(project)
                page_valid += 1

        logger.info("  page %d/%d: %d valid projects", idx, len(pages), page_valid)

    logger.info("Ollama technical extraction complete: %d total projects from %s",
                len(all_projects), pdf_path.name)
    return all_projects
