"""
Financial Data Normalizer.
Parses multi-format dates, handles negative/positive/accounting amount conventions,
and sanitizes text to neutralize CSV formula injection attacks.
"""
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Optional, Tuple


def clean_text(raw_text: Optional[str]) -> str:
    """
    Sanitize text strings and neutralize CSV formula injection characters.
    If string starts with '=', '+', '-', '@', '\t', or '\r', prefix with apostrophe.
    Guards against whitespace-stripping bypasses.
    """
    if raw_text is None:
        return ""
    raw = str(raw_text)
    if raw and raw[0] in ("=", "+", "-", "@", "\t", "\r"):
        # Prevent formula injection when exported/opened in Excel
        return "'" + raw.strip()
    cleaned = raw.strip()
    if cleaned and cleaned[0] in ("=", "+", "-", "@"):
        return "'" + cleaned
    return cleaned


def parse_financial_date(date_str: Optional[str]) -> date:
    """
    Parse date string supporting various international and banking date formats:
    - ISO 8601: YYYY-MM-DD
    - US Format: MM/DD/YYYY or MM-DD-YYYY
    - European Format: DD/MM/YYYY or DD-MM-YYYY
    - Textual: DD-Mon-YYYY (15-Oct-2026), Mon DD, YYYY (Oct 15, 2026)
    """
    if not date_str:
        raise ValueError("Missing or empty transaction date")

    cleaned = str(date_str).strip()
    if not cleaned:
        raise ValueError("Missing or empty transaction date")

    date_formats = [
        "%Y-%m-%d",       # 2026-10-15
        "%m/%d/%Y",       # 10/15/2026
        "%d/%m/%Y",       # 15/10/2026
        "%m-%d-%Y",       # 10-15-2026
        "%d-%m-%Y",       # 15-10-2026
        "%d-%b-%Y",       # 15-Oct-2026
        "%d %b %Y",       # 15 Oct 2026
        "%b %d, %Y",      # Oct 15, 2026
        "%b %d %Y",       # Oct 15 2026
        "%Y/%m/%d",       # 2026/10/15
        "%d.%m.%Y",       # 15.10.2026
        "%Y%m%d",         # 20261015
    ]

    for fmt in date_formats:
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue

    # Attempt regex date match if embedded in timestamp string
    iso_match = re.search(r"(\d{4})[-/](\d{2})[-/](\d{2})", cleaned)
    if iso_match:
        y, m, d = iso_match.groups()
        return date(int(y), int(m), int(d))

    raise ValueError(f"Unable to parse date string: '{date_str}'")


def parse_financial_amount(
    val_str: Optional[str],
    default_direction: Optional[str] = None,
) -> Tuple[Decimal, str, Optional[Decimal], Optional[Decimal]]:
    """
    Parse monetary amount string into exact fixed-point Decimal and direction:
    - Supports positive values: $1,250.00 -> 1250.00, CREDIT (or default)
    - Supports negative values: -$50.25 -> 50.25, DEBIT
    - Supports accounting parentheses: ($300.00) or (300.00) -> 300.00, DEBIT
    - Strips currency symbols ($, €, £, ¥, ₹) and comma thousands separators.

    Returns (magnitude_amount, direction, debit_amount, credit_amount).
    """
    if val_str is None:
        raise ValueError("Amount string is null")

    cleaned = str(val_str).strip()
    if not cleaned:
        raise ValueError("Amount string is empty")

    is_negative = False

    # Check for accounting parentheses e.g. (1,250.00) or ( 50.00 )
    if cleaned.startswith("(") and cleaned.endswith(")"):
        is_negative = True
        cleaned = cleaned[1:-1].strip()

    # Check for leading/trailing minus sign
    if cleaned.startswith("-") or cleaned.endswith("-"):
        is_negative = True
        cleaned = cleaned.replace("-", "").strip()
    elif cleaned.startswith("+"):
        cleaned = cleaned[1:].strip()

    # Strip currency symbols and whitespace
    cleaned = re.sub(r"[^\d.,]", "", cleaned)

    if not cleaned:
        raise ValueError(f"No numeric value found in amount: '{val_str}'")

    # Handle European decimal comma if used as decimal separator (e.g. 1.250,50 vs 1,250.50)
    if "," in cleaned and "." in cleaned:
        # Determine which is the decimal separator based on last position
        if cleaned.rfind(",") > cleaned.rfind("."):
            # 1.250,50 -> 1250.50
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            # 1,250.50 -> 1250.50
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned and "." not in cleaned:
        # Check if comma is decimal separator (e.g., 50,25) or thousands (1,000)
        parts = cleaned.split(",")
        if len(parts) == 2 and len(parts[1]) in (1, 2):
            cleaned = cleaned.replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")

    try:
        magnitude = Decimal(cleaned).quantize(Decimal("0.01"))
    except InvalidOperation:
        raise ValueError(f"Invalid monetary numerical format: '{val_str}'")

    if magnitude < 0:
        is_negative = True
        magnitude = abs(magnitude)

    # Determine direction: explicit negative sign always indicates DEBIT
    if is_negative:
        direction = "DEBIT"
    elif default_direction:
        direction = default_direction.upper()
    else:
        direction = "CREDIT"

    debit_amount = magnitude if direction == "DEBIT" else None
    credit_amount = magnitude if direction == "CREDIT" else None

    return magnitude, direction, debit_amount, credit_amount
