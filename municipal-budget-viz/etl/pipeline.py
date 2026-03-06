#!/usr/bin/env python3
"""ETL pipeline CLI for Greek municipal budget PDFs.

Usage:
  python pipeline.py --input ../budget_past/ --type auto
  python pipeline.py --input ../budget_plan/ --type auto
  python pipeline.py --input path/to/single.pdf --type budget
  python pipeline.py --input path/to/single.pdf --type technical
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger("pipeline")

# ---------------------------------------------------------------------------
# Type detection helpers
# ---------------------------------------------------------------------------

_BUDGET_KEYWORDS = (
    "δαπανεσ", "δαπανών", "προυπολογισμ", "τευχοσ", "265_"
)
_TECHNICAL_KEYWORDS = (
    "τεχνικο", "τεχνικό", "techniko", "ty_"
)


def detect_doc_type(pdf_path: Path) -> str:
    """Return 'BUDGET' or 'TECHNICAL_PROGRAM' based on filename heuristics.

    Falls back to reading the first page with pdfplumber if the filename
    is ambiguous.
    """
    lower_name = pdf_path.name.lower()

    if any(kw in lower_name for kw in _BUDGET_KEYWORDS):
        return "BUDGET"
    if any(kw in lower_name for kw in _TECHNICAL_KEYWORDS):
        return "TECHNICAL_PROGRAM"

    # Try first-page text
    try:
        import pdfplumber
        with pdfplumber.open(str(pdf_path)) as pdf:
            text = (pdf.pages[0].extract_text() or "").lower()
        if any(kw in text for kw in ("προϋπολογισμ", "δαπανεσ", "εσοδα")):
            return "BUDGET"
        if "τεχνικό πρόγραμμα" in text or "τεχνικο προγραμμα" in text:
            return "TECHNICAL_PROGRAM"
    except Exception as exc:
        logger.debug("First-page detection failed for %s: %s", pdf_path.name, exc)

    logger.warning("Cannot auto-detect type for %s; defaulting to BUDGET", pdf_path.name)
    return "BUDGET"


def extract_year(pdf_path: Path) -> int:
    """Try to extract the budget year from the filename."""
    match = re.search(r"(202\d)", pdf_path.name)
    if match:
        return int(match.group(1))
    return 2025  # safe default


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def process_pdf(pdf_path: Path, doc_type: str) -> None:
    from loaders.db_loader import register_document, load_budget, load_technical

    year = extract_year(pdf_path)
    municipality = "Αχαρνές"  # TODO: make configurable or detect from PDF

    logger.info("Processing %s  type=%s  year=%d", pdf_path.name, doc_type, year)

    document_id = register_document(
        filename=pdf_path.name,
        doc_type=doc_type,
        municipality=municipality,
        year=year,
    )
    logger.info("Registered document id=%d", document_id)

    if doc_type == "BUDGET":
        from extractors.budget_extractor import extract_budget
        result = extract_budget(pdf_path)
        load_budget(document_id, result["categories"], result["items"])

    elif doc_type == "TECHNICAL_PROGRAM":
        from extractors.technical_extractor import extract_technical
        result = extract_technical(pdf_path)
        load_technical(document_id, result["projects"])

    else:
        logger.error("Unknown doc_type: %s", doc_type)


def collect_pdfs(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    return sorted(input_path.glob("*.pdf"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Municipal budget PDF ETL pipeline")
    parser.add_argument("--input", required=True, help="PDF file or directory of PDFs")
    parser.add_argument(
        "--type",
        choices=["auto", "budget", "technical"],
        default="auto",
        help="Document type (default: auto-detect)",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        logger.error("Input path does not exist: %s", input_path)
        sys.exit(1)

    pdfs = collect_pdfs(input_path)
    if not pdfs:
        logger.warning("No PDF files found at %s", input_path)
        sys.exit(0)

    type_map = {"budget": "BUDGET", "technical": "TECHNICAL_PROGRAM", "auto": None}
    forced_type = type_map[args.type]

    success, failure = 0, 0
    for pdf in pdfs:
        doc_type = forced_type or detect_doc_type(pdf)
        try:
            process_pdf(pdf, doc_type)
            success += 1
        except Exception as exc:
            logger.error("Failed to process %s: %s", pdf.name, exc, exc_info=True)
            failure += 1

    logger.info("Done. success=%d  failure=%d", success, failure)
    if failure:
        sys.exit(1)


if __name__ == "__main__":
    main()
