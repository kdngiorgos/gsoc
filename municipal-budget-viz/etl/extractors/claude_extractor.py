"""Claude Haiku backend for Greek municipal PDF extraction.

Activated automatically when ANTHROPIC_API_KEY is set in the environment.
Mirrors the public API of ollama_extractor.py exactly.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

import anthropic

from extractors.ollama_extractor import (
    _BUDGET_PROMPT,
    _TECHNICAL_PROMPT,
    _read_pages,
    _validate_budget_item,
    _validate_project,
)

logger = logging.getLogger(__name__)

CLAUDE_MODEL = "claude-haiku-4-5-20251001"

_SYSTEM_PROMPT = "You are a data extraction assistant. Always respond with valid JSON only."


def _call_claude(client: anthropic.Anthropic, prompt_template: str, text: str) -> Optional[Dict]:
    """Call Claude Haiku with the given prompt template and text chunk.

    Returns parsed JSON dict or None on failure.
    """
    prompt = prompt_template.format(text=text)
    try:
        msg = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=8192,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        if msg.stop_reason == "max_tokens":
            logger.warning("Claude hit max_tokens — response truncated, page skipped")
            return None
        raw = msg.content[0].text.strip()
        # Strip markdown code fences if present (```json ... ``` or ``` ... ```)
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
            if raw.endswith("```"):
                raw = raw[: raw.rfind("```")]
        return json.loads(raw)
    except Exception as exc:
        logger.error("Claude call failed: %s", exc)
        return None


def extract_budget_claude(pdf_path: Path, max_pages: Optional[int] = None) -> List[Dict]:
    """Extract budget items from a PDF using Claude Haiku.

    Returns a flat list of normalised item dicts.
    """
    pdf_path = Path(pdf_path)
    logger.info("Claude budget extraction: model=%s file=%s", CLAUDE_MODEL, pdf_path.name)

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

    pages = _read_pages(pdf_path, max_pages=max_pages)
    logger.info("  %d pages to process", len(pages))

    all_items: List[Dict] = []
    for idx, page_text in enumerate(pages, 1):
        result = _call_claude(client, _BUDGET_PROMPT, page_text)
        if result is None:
            logger.warning("  page %d/%d: Claude returned no result", idx, len(pages))
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

    logger.info("Claude budget extraction complete: %d total items from %s",
                len(all_items), pdf_path.name)
    return all_items


def extract_technical_claude(pdf_path: Path, max_pages: Optional[int] = None) -> List[Dict]:
    """Extract technical projects from a PDF using Claude Haiku.

    Returns a flat list of normalised project dicts.
    """
    pdf_path = Path(pdf_path)
    logger.info("Claude technical extraction: model=%s file=%s", CLAUDE_MODEL, pdf_path.name)

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

    pages = _read_pages(pdf_path, max_pages=max_pages)
    logger.info("  %d pages to process", len(pages))

    all_projects: List[Dict] = []
    for idx, page_text in enumerate(pages, 1):
        result = _call_claude(client, _TECHNICAL_PROMPT, page_text)
        if result is None:
            logger.warning("  page %d/%d: Claude returned no result", idx, len(pages))
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

    logger.info("Claude technical extraction complete: %d total projects from %s",
                len(all_projects), pdf_path.name)
    return all_projects
