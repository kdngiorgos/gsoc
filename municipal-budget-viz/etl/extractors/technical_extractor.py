"""Extract structured data from Greek Municipal Technical Program PDFs.

Handles documents of type TECHNICAL_PROGRAM (Τεχνικό Πρόγραμμα).

Extraction strategy: pdfplumber.extract_text() per page → Claude Haiku (if
ANTHROPIC_API_KEY is set) or Ollama → structured JSON.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


def _backend() -> Callable:
    """Return the active extraction function based on available credentials."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        from extractors.claude_extractor import extract_technical_claude
        return extract_technical_claude
    from extractors.ollama_extractor import extract_technical_ollama
    return extract_technical_ollama


def extract_technical(pdf_path: Path, max_pages: Optional[int] = None) -> List[Dict]:
    """Extract technical program data from a PDF file.

    Returns a flat list of unified item dicts:
      [{code, description, parentCode, amounts: [{label, amount}]}]
    """
    pdf_path = Path(pdf_path)
    logger.info("Extracting technical program from %s", pdf_path.name)

    projects = _backend()(pdf_path, max_pages=max_pages)

    if not projects:
        logger.warning("No projects found in %s", pdf_path.name)
        return []

    result: List[Dict] = []
    for project in projects:
        result.append({
            "code": project.get("projectCode", ""),
            "description": project.get("description", ""),
            "parentCode": None,
            "amounts": project.get("items", []),
        })

    logger.info("Extracted %d items from %s", len(result), pdf_path.name)
    return result
