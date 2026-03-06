"""Parse and reconstruct the KAE (Κωδικός Άρθρου Εξόδου) hierarchy.

Greek municipal budget codes follow a hierarchical structure encoded in
the code string itself. Two main formats are present in our PDFs:

Format A — ΔΑΠΑΝΕΣ / expense budget:
  Level 0 (Section)  : "00"             2-digit section
  Level 1 (Group)    : "00-60"          dash + 2-digit group
  Level 2 (Article)  : "00-603"         3-digit article
  Level 3 (Sub-item) : "00-6031"        4-digit sub-item
  Level 4 (Detail)   : "00-6031.0001"   dot + 4-digit detail

Format B — ΕΣΟΔΑ / income budget (Τεύχος):
  "0111"             4-digit code
  "0111.00000"       dot + 5-digit sub-code

The parent of a code is derived by truncating the last segment:
  "00-6031.0001" -> "00-6031"
  "00-6031"      -> "00-603"
  "00-603"       -> "00-60"
  "00-60"        -> "00"
  "0111.00000"   -> "0111"
"""

import re
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class KaeNode:
    code: str
    description: str
    level: int
    parent_code: Optional[str]


_FORMAT_A = re.compile(
    r"^(\d{2})(?:-(\d{2,4})(?:\.(\d{4}))?)?$"
)
_FORMAT_B = re.compile(
    r"^(\d{4})(?:\.(\d{5}))?$"
)


def get_parent_code(code: str) -> Optional[str]:
    """Return the parent KAE code, or None if this is a root code."""
    code = code.strip()

    # Format A: "00-6031.0001"
    if "-" in code:
        if "." in code:
            # "00-6031.0001" -> "00-6031"
            return code.rsplit(".", 1)[0]
        # "00-6031" -> "00-603" -> "00-60" -> "00"
        prefix, digits = code.split("-", 1)
        if len(digits) > 2:
            return f"{prefix}-{digits[:-1]}"
        # "00-60" -> "00"
        return prefix

    # Format B: "0111.00000"
    if "." in code:
        return code.rsplit(".", 1)[0]

    # Root codes: "00", "0111" — no parent
    return None


def get_level(code: str) -> int:
    """Return the hierarchy level (0 = root section)."""
    code = code.strip()
    if "." in code:
        return 4 if "-" in code else 1  # A=4, B=1 (leaf)
    if "-" in code:
        prefix, digits = code.split("-", 1)
        return len(digits) - 1  # 2->1, 3->2, 4->3
    # No dash, no dot: root
    return 0


def build_category_tree(
    rows: List[Dict[str, str]]
) -> List[KaeNode]:
    """Convert a list of {code, description} dicts to KaeNode list with parents.

    Rows should be in document order (top-down). Unknown parent codes are
    represented as None (treated as roots during DB insertion).
    """
    seen_codes: set[str] = set()
    nodes: List[KaeNode] = []

    for row in rows:
        code = row.get("code", "").strip()
        description = row.get("description", "").strip()
        if not code:
            continue
        if code in seen_codes:
            continue
        seen_codes.add(code)
        parent = get_parent_code(code)
        level = get_level(code)
        nodes.append(KaeNode(
            code=code,
            description=description,
            level=level,
            parent_code=parent,
        ))

    return nodes
