"""Extract structured data from Greek municipal budget PDFs.

Handles documents of type BUDGET (Προϋπολογισμός / ΔΑΠΑΝΕΣ).

Extraction strategy: pdfplumber.extract_text() per page → Claude Haiku (if
ANTHROPIC_API_KEY is set) or Ollama → structured JSON.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

_SUBTOTAL_RE = re.compile(r"σύνολ[οα]|άθροισμα", re.IGNORECASE)

_AMOUNT_FIELDS = [
    ("amount2024",    "ΠΥ 2024"),
    ("amountMidYear", "Αναμορφωμένος"),
    ("amount2025",    "ΠΥ 2025"),
    ("amountVariance","Διαφορά"),
]


def _backend() -> Callable:
    """Return the active extraction function based on available credentials."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        from extractors.claude_extractor import extract_budget_claude
        return extract_budget_claude
    from extractors.ollama_extractor import extract_budget_ollama
    return extract_budget_ollama


def _derive_parent_code(code: str) -> Optional[str]:
    """Derive parentCode from KAE code structure.

    Examples:
      "00"           → None
      "00-60"        → "00"
      "00-603"       → "00-60"
      "00-6031"      → "00-603"
      "00-6031.0001" → "00-6031"
    """
    if "." in code:
        return code.rsplit(".", 1)[0]
    if "-" in code:
        prefix, suffix = code.split("-", 1)
        if len(suffix) > 2:
            return f"{prefix}-{suffix[:-1]}"
        return prefix
    return None


def extract_budget(pdf_path: Path, max_pages: Optional[int] = None) -> List[Dict]:
    """Extract budget data from a PDF file.

    Returns a flat list of unified item dicts:
      [{code, description, parentCode, amounts: [{label, amount}]}]
    """
    pdf_path = Path(pdf_path)
    logger.info("Extracting budget from %s", pdf_path.name)

    raw = _backend()(pdf_path, max_pages=max_pages)

    result: List[Dict] = []
    for r in raw:
        if _SUBTOTAL_RE.search(r.get("description", "")):
            continue

        amounts = [
            {"label": label, "amount": r[field]}
            for field, label in _AMOUNT_FIELDS
            if r.get(field) is not None
        ]
        if not amounts:
            continue

        code = r.get("code", "")
        result.append({
            "code": code,
            "description": r.get("description", ""),
            "parentCode": _derive_parent_code(code),
            "amounts": amounts,
        })

    logger.info("Extracted %d items from %s", len(result), pdf_path.name)
    return result
