#!/usr/bin/env python3
"""ETL pipeline CLI for Greek municipal budget PDFs.

Usage:
  # Manual folder / file
  python pipeline.py --input ../budget_past/ --type auto
  python pipeline.py --input ../budget_plan/ --type auto
  python pipeline.py --input path/to/single.pdf --type budget

  # Auto-discover from Diavgeia
  python pipeline.py --municipality "Αχαρνές" --year 2025
  python pipeline.py --municipality "Αχαρνές" --year 2025 --dest /tmp/pdfs
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
import tempfile
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
    "δαπανεσ", "δαπανών", "προυπολογισμ", "τεύχ", "265_", "2_"
)
_TECHNICAL_KEYWORDS = (
    "τεχνικο", "τεχνικό", "techniko", "ty_", "1_"
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

    # Try first few pages' text
    try:
        import pdfplumber
        with pdfplumber.open(str(pdf_path)) as pdf:
            text = " ".join(
                (p.extract_text() or "") for p in pdf.pages[:3]
            ).lower()
        if any(kw in text for kw in ("προϋπολογισμ", "δαπανεσ", "εσοδα")):
            return "BUDGET"
        if any(kw in text for kw in ("τεχνικ", "εργων", "εργών", "technical")):
            return "TECHNICAL_PROGRAM"
    except Exception as exc:
        logger.debug("Content-based detection failed for %s: %s", pdf_path.name, exc)

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

def process_pdf(
    pdf_path: Path,
    doc_type: str,
    municipality: str = "Αχαρνές",
    ada_code: str | None = None,
    max_pages: int | None = None,
) -> None:
    from loaders.db_loader import register_document, load_items

    year = extract_year(pdf_path)

    logger.info("Processing %s  type=%s  year=%d", pdf_path.name, doc_type, year)

    document_id, is_new = register_document(
        filename=pdf_path.name,
        doc_type=doc_type,
        municipality=municipality,
        year=year,
        ada_code=ada_code,
    )
    if not is_new:
        logger.warning("Skipping extraction — document already loaded (id=%d).", document_id)
        return
    logger.info("Registered document id=%d", document_id)

    if doc_type == "BUDGET":
        from extractors.budget_extractor import extract_budget
        items = extract_budget(pdf_path, max_pages=max_pages)
    elif doc_type == "TECHNICAL_PROGRAM":
        from extractors.technical_extractor import extract_technical
        items = extract_technical(pdf_path, max_pages=max_pages)
    else:
        logger.error("Unknown doc_type: %s", doc_type)
        return

    load_items(document_id, items)


def collect_pdfs(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    return sorted(input_path.glob("*.pdf"))


# ---------------------------------------------------------------------------
# Diavgeia discovery mode
# ---------------------------------------------------------------------------

_DIAVGEIA_TYPE_MAP = {
    "Β1": "BUDGET",
    "Β2": "BUDGET",
    "Ε":  "TECHNICAL_PROGRAM",
}


def run_diavgeia_mode(municipality: str, year: int, dest_dir: Path, forced_type: str | None) -> None:
    """Discover, download, and process PDFs from Diavgeia."""
    sys.path.insert(0, str(Path(__file__).parent))
    from discovery.diavgeia_client import discover_and_download

    logger.info("Diavgeia mode: municipality=%s  year=%d", municipality, year)
    decisions = discover_and_download(municipality, year, dest_dir)

    if not decisions:
        logger.warning("No decisions found for %s %d on Diavgeia", municipality, year)
        return

    success, failure = 0, 0
    for dec in decisions:
        pdf_path = Path(dec["pdf_path"])
        ada_code = dec["ada"]
        doc_type = forced_type or _DIAVGEIA_TYPE_MAP.get(dec["doc_type"]) or detect_doc_type(pdf_path)
        try:
            process_pdf(pdf_path, doc_type, municipality=municipality, ada_code=ada_code)
            success += 1
        except Exception as exc:
            logger.error("Failed to process %s: %s", pdf_path.name, exc, exc_info=True)
            failure += 1

    logger.info("Done. success=%d  failure=%d", success, failure)
    if failure:
        sys.exit(1)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Municipal budget PDF ETL pipeline")

    # Input source — exactly one of --input or --municipality
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", help="PDF file or directory of PDFs (manual mode)")
    source.add_argument(
        "--municipality",
        help="Municipality name in Greek (Diavgeia discovery mode)",
    )

    parser.add_argument(
        "--year",
        type=int,
        default=2025,
        help="Budget year for Diavgeia search (default: 2025)",
    )
    parser.add_argument(
        "--dest",
        default=None,
        help="Download directory for Diavgeia PDFs (default: system temp dir)",
    )
    parser.add_argument(
        "--type",
        choices=["auto", "budget", "technical"],
        default="auto",
        help="Document type override (default: auto-detect)",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Limit extraction to first N pages (for fast testing on large files)",
    )
    parser.add_argument(
        "--manual-municipality",
        default=None,
        metavar="MUNICIPALITY",
        help="Municipality name for manual --input mode (e.g. 'Παλαιό Φάληρο'). "
             "Required when --input is used; defaults to 'Άγνωστος' with a warning if omitted.",
    )
    args = parser.parse_args()

    type_map = {"budget": "BUDGET", "technical": "TECHNICAL_PROGRAM", "auto": None}
    forced_type = type_map[args.type]

    # ---- Diavgeia discovery mode ----
    if args.municipality:
        dest_dir = Path(args.dest) if args.dest else Path(tempfile.mkdtemp(prefix="diavgeia_"))
        run_diavgeia_mode(args.municipality, args.year, dest_dir, forced_type)
        return

    # ---- Manual folder / file mode ----
    input_path = Path(args.input)
    if not input_path.exists():
        logger.error("Input path does not exist: %s", input_path)
        sys.exit(1)

    municipality = args.manual_municipality
    if not municipality:
        logger.warning(
            "--manual-municipality not provided; storing municipality as 'Άγνωστος'. "
            "Re-run with --manual-municipality 'Παλαιό Φάληρο' (etc.) for correct data."
        )
        municipality = "Άγνωστος"

    pdfs = collect_pdfs(input_path)
    if not pdfs:
        logger.warning("No PDF files found at %s", input_path)
        sys.exit(0)

    success, failure = 0, 0
    for pdf in pdfs:
        doc_type = forced_type or detect_doc_type(pdf)
        try:
            process_pdf(pdf, doc_type, municipality=municipality, max_pages=args.max_pages)
            success += 1
        except Exception as exc:
            logger.error("Failed to process %s: %s", pdf.name, exc, exc_info=True)
            failure += 1

    logger.info("Done. success=%d  failure=%d", success, failure)
    if failure:
        sys.exit(1)


if __name__ == "__main__":
    main()
