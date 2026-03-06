"""Parse European-format monetary amounts used in Greek municipal budget PDFs.

European format uses:
  - period (.) as thousands separator
  - comma (,) as decimal separator

Examples:
  "1.661.761,40"  ->  Decimal("1661761.40")
  "71.372,00"     ->  Decimal("71372.00")
  "492.293,95"    ->  Decimal("492293.95")
  "0,00"          ->  Decimal("0.00")
"""

import re
from decimal import Decimal, InvalidOperation
from typing import Optional


_AMOUNT_RE = re.compile(r"^-?[\d.,]+$")


def parse_amount(value: str) -> Optional[Decimal]:
    """Convert a European-formatted amount string to Decimal.

    Returns None if the value is empty, whitespace-only, or cannot be parsed.
    """
    if not value:
        return None
    cleaned = value.strip().replace("\xa0", "").replace(" ", "")
    if not cleaned or cleaned in ("-", "—", ".."):
        return None
    if not _AMOUNT_RE.match(cleaned):
        return None
    # Remove thousands separators (periods) then swap decimal comma to period
    normalized = cleaned.replace(".", "").replace(",", ".")
    try:
        return Decimal(normalized)
    except InvalidOperation:
        return None
