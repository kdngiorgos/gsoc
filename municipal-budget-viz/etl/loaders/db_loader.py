"""Load extracted budget data into PostgreSQL.

Uses psycopg2 directly (no ORM) for the ETL side to avoid coupling to
Prisma's migration state. Prisma manages the schema; we just INSERT.
"""

from __future__ import annotations

import logging
import os
from decimal import Decimal
from typing import Dict, List, Optional

import psycopg2
import psycopg2.extras

from transformers.kae_parser import KaeNode

logger = logging.getLogger(__name__)


def get_connection():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL environment variable is not set")
    return psycopg2.connect(url)


# ---------------------------------------------------------------------------
# Budget loader
# ---------------------------------------------------------------------------

def _upsert_category(cur, node: KaeNode, code_to_id: Dict[str, int]) -> int:
    """Insert or update a BudgetCategory row; return its DB id."""
    parent_id = code_to_id.get(node.parent_code) if node.parent_code else None
    cur.execute(
        """
        INSERT INTO "BudgetCategory" (code, description, level, "parentId")
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (code) DO UPDATE
          SET description = EXCLUDED.description,
              level       = EXCLUDED.level,
              "parentId"  = EXCLUDED."parentId"
        RETURNING id
        """,
        (node.code, node.description, node.level, parent_id),
    )
    return cur.fetchone()[0]


def load_budget(
    document_id: int,
    categories: List[KaeNode],
    items: List[Dict],
    conn=None,
) -> None:
    """Persist budget categories and items for the given document."""
    own_conn = conn is None
    if own_conn:
        conn = get_connection()

    try:
        with conn:
            with conn.cursor() as cur:
                # Insert categories in document order (parents before children
                # because build_category_tree preserves document order and
                # parents appear before their children in the PDF)
                code_to_id: Dict[str, int] = {}
                for node in categories:
                    db_id = _upsert_category(cur, node, code_to_id)
                    code_to_id[node.code] = db_id

                # Insert budget items
                insert_item = """
                    INSERT INTO "BudgetItem"
                      ("documentId", "categoryId", description,
                       amount2024, "amountMidYear", amount2025, "amountVariance")
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """
                for item in items:
                    category_id = code_to_id.get(item["code"])
                    if category_id is None:
                        logger.debug("No category id for code %s, skipping item", item["code"])
                        continue
                    cur.execute(insert_item, (
                        document_id,
                        category_id,
                        item.get("description", ""),
                        item.get("amount2024"),
                        item.get("amountMidYear"),
                        item.get("amount2025"),
                        item.get("amountVariance"),
                    ))
                logger.info("Loaded %d items for document %d", len(items), document_id)
    finally:
        if own_conn:
            conn.close()


# ---------------------------------------------------------------------------
# Technical program loader
# ---------------------------------------------------------------------------

def load_technical(
    document_id: int,
    projects: List[Dict],
    conn=None,
) -> None:
    """Persist technical projects for the given document."""
    own_conn = conn is None
    if own_conn:
        conn = get_connection()

    try:
        with conn:
            with conn.cursor() as cur:
                for project in projects:
                    cur.execute(
                        """
                        INSERT INTO "TechnicalProject"
                          ("documentId", "projectCode", description, section, "budgetRef")
                        VALUES (%s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        (
                            document_id,
                            project["projectCode"],
                            project.get("description", ""),
                            project.get("section", ""),
                            project.get("budgetRef"),
                        ),
                    )
                    project_id = cur.fetchone()[0]

                    for item in project.get("items", []):
                        cur.execute(
                            """
                            INSERT INTO "TechnicalProjectItem"
                              ("projectId", label, amount)
                            VALUES (%s, %s, %s)
                            """,
                            (project_id, item["label"], item["amount"]),
                        )
                logger.info("Loaded %d projects for document %d", len(projects), document_id)
    finally:
        if own_conn:
            conn.close()


# ---------------------------------------------------------------------------
# Document registry
# ---------------------------------------------------------------------------

def register_document(
    filename: str,
    doc_type: str,
    municipality: str,
    year: int,
    conn=None,
) -> int:
    """Insert a Document record and return its id."""
    own_conn = conn is None
    if own_conn:
        conn = get_connection()

    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO "Document" (filename, "docType", municipality, year)
                    VALUES (%s, %s::"DocType", %s, %s)
                    RETURNING id
                    """,
                    (filename, doc_type, municipality, year),
                )
                return cur.fetchone()[0]
    finally:
        if own_conn:
            conn.close()
