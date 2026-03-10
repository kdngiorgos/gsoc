"""Diavgeia REST API client for discovering municipal budget documents.

Diavgeia (https://diavgeia.gov.gr) is the Greek government transparency portal.
All 332 municipalities are required to publish budget decisions there.

Decision types relevant to budgets:
  Β1 — Budget approval (Έγκριση Προϋπολογισμού)
  Β2 — Budget revision
  Ε  — Technical program (Τεχνικό Πρόγραμμα)

Usage:
  python -m discovery.diavgeia_client --municipality "Αχαρνές" --year 2025
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

import requests

logger = logging.getLogger(__name__)

_BASE = "https://diavgeia.gov.gr/luminapi/api/"
_DOWNLOAD_BASE = "https://diavgeia.gov.gr"
_SESSION_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "municipal-budget-viz/1.0 (GSoC PoC)",
}
_TIMEOUT = 30
_RETRY_DELAY = 2  # seconds between retries


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _get(path: str, params: Optional[dict] = None) -> dict:
    url = urljoin(_BASE, path)
    for attempt in range(3):
        try:
            resp = requests.get(url, params=params, headers=_SESSION_HEADERS, timeout=_TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            if attempt == 2:
                raise
            logger.warning("Request failed (%s), retrying in %ds…", exc, _RETRY_DELAY)
            time.sleep(_RETRY_DELAY)
    return {}  # unreachable


# ---------------------------------------------------------------------------
# Municipality lookup
# ---------------------------------------------------------------------------

def list_municipalities() -> list[dict]:
    """Return all municipalities registered on Diavgeia.

    Each item has: uid, label (Greek name), category.
    """
    data = _get("organizations", {"category": "MUNICIPALITY", "page": 0, "size": 500})
    orgs = data.get("organizations") or data.get("items") or []
    if not orgs and isinstance(data, list):
        orgs = data
    return [
        {
            "uid": org.get("uid") or org.get("organizationCode"),
            "label": org.get("label") or org.get("organizationName", ""),
        }
        for org in orgs
        if org.get("uid") or org.get("organizationCode")
    ]


def find_municipality_uid(name: str) -> Optional[str]:
    """Find a municipality's Diavgeia UID by (partial) Greek name."""
    municipalities = list_municipalities()
    name_lower = name.lower()
    # Exact match first
    for m in municipalities:
        if m["label"].lower() == name_lower:
            return m["uid"]
    # Partial match
    for m in municipalities:
        if name_lower in m["label"].lower():
            return m["uid"]
    return None


# ---------------------------------------------------------------------------
# Decision search
# ---------------------------------------------------------------------------

_DECISION_TYPES = {
    "budget": ["Β1", "Β2"],
    "technical": ["Ε"],
    "all": ["Β1", "Β2", "Ε"],
}


def search_decisions(
    org_uid: str,
    year: int,
    doc_types: list[str] = ("Β1", "Β2", "Ε"),
    max_results: int = 50,
) -> list[dict]:
    """Search Diavgeia for budget/technical program decisions.

    Returns list of dicts with: ada, title, issue_date, pdf_url, doc_type.
    """
    results = []
    for dtype in doc_types:
        page = 0
        while len(results) < max_results:
            try:
                data = _get("search/advanced", {
                    "q": f"issueYear:{year}",
                    "org": org_uid,
                    "decisionTypeUid": dtype,
                    "page": page,
                    "size": min(20, max_results - len(results)),
                    "sort": "recent",
                })
            except Exception as exc:
                logger.warning("Search failed for type %s: %s", dtype, exc)
                break

            decisions = data.get("decisions") or data.get("items") or []
            if not decisions:
                break

            for dec in decisions:
                ada = dec.get("ada") or dec.get("decisionId", "")
                results.append({
                    "ada": ada,
                    "title": dec.get("subject") or dec.get("title", ""),
                    "issue_date": dec.get("issueDate") or dec.get("publicationTimestamp", ""),
                    "pdf_url": f"{_DOWNLOAD_BASE}/decision/view/{ada}",
                    "doc_type": dtype,
                })

            if len(decisions) < 20:
                break
            page += 1

    return results


# ---------------------------------------------------------------------------
# PDF download
# ---------------------------------------------------------------------------

def download_pdf(ada: str, dest_dir: Path) -> Path:
    """Download a Diavgeia decision PDF and save to dest_dir/{ada}.pdf.

    Returns the path to the saved file.
    """
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    safe_ada = ada.replace("/", "_")
    dest_file = dest_dir / f"{safe_ada}.pdf"

    if dest_file.exists():
        logger.info("Already downloaded: %s", dest_file)
        return dest_file

    url = urljoin(_BASE, f"decisions/{ada}/document")
    logger.info("Downloading %s → %s", ada, dest_file)

    for attempt in range(3):
        try:
            resp = requests.get(
                url,
                headers={**_SESSION_HEADERS, "Accept": "application/pdf"},
                timeout=60,
                stream=True,
            )
            resp.raise_for_status()
            with open(dest_file, "wb") as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    f.write(chunk)
            return dest_file
        except requests.RequestException as exc:
            if attempt == 2:
                raise
            logger.warning("Download failed (%s), retrying…", exc)
            time.sleep(_RETRY_DELAY)

    raise RuntimeError(f"Failed to download {ada}")  # unreachable


# ---------------------------------------------------------------------------
# High-level helper
# ---------------------------------------------------------------------------

def discover_and_download(municipality: str, year: int, dest_dir: Path) -> list[dict]:
    """Find a municipality on Diavgeia, search budget decisions, download PDFs.

    Returns list of dicts: {ada, title, issue_date, pdf_path, doc_type}
    """
    logger.info("Looking up municipality '%s' on Diavgeia…", municipality)
    uid = find_municipality_uid(municipality)
    if not uid:
        raise ValueError(f"Municipality '{municipality}' not found on Diavgeia")
    logger.info("Found UID: %s", uid)

    decisions = search_decisions(uid, year)
    logger.info("Found %d decisions for %s %d", len(decisions), municipality, year)

    result = []
    for dec in decisions:
        try:
            pdf_path = download_pdf(dec["ada"], dest_dir)
            result.append({**dec, "pdf_path": pdf_path})
        except Exception as exc:
            logger.error("Failed to download %s: %s", dec["ada"], exc)

    return result


# ---------------------------------------------------------------------------
# CLI entry point (for manual testing)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Diavgeia decision discovery")
    parser.add_argument("--municipality", default="Αχαρνές")
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument("--list-orgs", action="store_true", help="List all municipalities")
    parser.add_argument("--download", action="store_true", help="Download PDFs")
    parser.add_argument("--dest", default="/tmp/diavgeia_pdfs", help="Download directory")
    args = parser.parse_args()

    if args.list_orgs:
        orgs = list_municipalities()
        print(f"Found {len(orgs)} municipalities")
        for o in orgs[:20]:
            print(f"  {o['uid']:20s}  {o['label']}")
        if len(orgs) > 20:
            print(f"  … and {len(orgs) - 20} more")
        sys.exit(0)

    uid = find_municipality_uid(args.municipality)
    if not uid:
        print(f"Municipality '{args.municipality}' not found", file=sys.stderr)
        sys.exit(1)

    print(f"Municipality: {args.municipality}  UID: {uid}")
    decisions = search_decisions(uid, args.year)
    print(f"\nFound {len(decisions)} decisions for {args.year}:")
    for d in decisions:
        print(f"  [{d['doc_type']}] {d['ada']:<25s}  {d['issue_date'][:10] if d['issue_date'] else '?':10s}  {d['title'][:60]}")

    if args.download and decisions:
        dest = Path(args.dest)
        print(f"\nDownloading PDFs to {dest}…")
        for d in decisions:
            try:
                path = download_pdf(d["ada"], dest)
                print(f"  ✓ {path.name}")
            except Exception as e:
                print(f"  ✗ {d['ada']}: {e}")
