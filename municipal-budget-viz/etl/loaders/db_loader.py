"""Load extracted budget data into PostgreSQL.

Uses psycopg2 directly (no ORM) for the ETL side to avoid coupling to
Prisma's migration state. Prisma manages the schema; we just INSERT.
"""

from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional

import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)


def get_connection():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL environment variable is not set")
    return psycopg2.connect(url)


# ---------------------------------------------------------------------------
# Unified loader
# ---------------------------------------------------------------------------

def load_items(
    document_id: int,
    items: List[Dict],
    conn=None,
) -> None:
    """Persist unified items for the given document.

    items: [{code, description, parentCode, amounts: [{label, amount}]}]
    """
    own_conn = conn is None
    if own_conn:
        conn = get_connection()

    try:
        with conn:
            with conn.cursor() as cur:
                for item in items:
                    cur.execute(
                        """
                        INSERT INTO "Item" ("documentId", code, description, "parentCode")
                        VALUES (%s, %s, %s, %s)
                        RETURNING id
                        """,
                        (
                            document_id,
                            item["code"],
                            item.get("description", ""),
                            item.get("parentCode"),
                        ),
                    )
                    item_id = cur.fetchone()[0]

                    for amt in item.get("amounts", []):
                        cur.execute(
                            """
                            INSERT INTO "ItemAmount" ("itemId", label, amount)
                            VALUES (%s, %s, %s)
                            """,
                            (item_id, amt["label"], amt["amount"]),
                        )
        logger.info("Loaded %d items for document %d", len(items), document_id)
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
    ada_code: Optional[str] = None,
    conn=None,
) -> tuple[int, bool]:
    """Insert or find a Document record.

    Returns (id, is_new). If a document with the same (filename, municipality,
    year) already exists the existing id is returned and is_new=False.
    """
    own_conn = conn is None
    if own_conn:
        conn = get_connection()

    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id FROM "Document"
                    WHERE filename = %s AND municipality = %s AND year = %s
                    """,
                    (filename, municipality, year),
                )
                row = cur.fetchone()
                if row:
                    logger.warning(
                        "Document already in DB (id=%d, filename=%s, municipality=%s, year=%d); skipping.",
                        row[0], filename, municipality, year,
                    )
                    return row[0], False

                cur.execute(
                    """
                    INSERT INTO "Document" (filename, "docType", municipality, year, "adaCode")
                    VALUES (%s, %s::"DocType", %s, %s, %s)
                    RETURNING id
                    """,
                    (filename, doc_type, municipality, year, ada_code),
                )
                return cur.fetchone()[0], True
    finally:
        if own_conn:
            conn.close()
