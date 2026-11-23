"""
Financial Text Sanitization & Prompt Injection Protection Module.
Normalizes merchant strings, extracts reference tokens, masks sensitive data,
and wraps untrusted transaction descriptions in strict structural delimiters.
"""
import re
from typing import List, Optional

# Known payment rail and aggregator noise prefixes
PREFIX_PATTERNS = [
    r"^POS\s+(?:PURCHASE|DEBIT|CREDIT|AUTH)\s+",
    r"^CHECKCARD\s+\d+\s+",
    r"^DEBIT\s+CARD\s+PURCHASE\s+",
    r"^ACH\s+(?:DEBIT|CREDIT|PAYMENT|TRANS)\s+",
    r"^WIRE\s+(?:OUT|IN|TRANS)\s+",
    r"^ONLINE\s+BANKING\s+TRANSFER\s+",
    r"^DIRECT\s+DEP(?:OSIT)?\s+",
    r"^SQ\s*\*\s*",
    r"^TST\s*\*\s*",
    r"^PAYPAL\s*\*\s*",
    r"^STRIPE\s*\*\s*",
    r"^AMZN\s+Mktp\s*",
    r"^SP\s*\*\s*",
    r"^INTL\s+TXN\s*",
]

# Trailing location, store numbers, phone numbers
TRAILING_PATTERNS = [
    r"\s+#\d+",
    r"\s+STORE\s*#?\d+",
    r"\s+LOC\s*#?\d+",
    r"\s+\d{3}-\d{3}-\d{4}",
    r"\s+[A-Z]{2}\s+\d{5}(?:-\d{4})?$",  # State + ZIP
    r"\s+\d{2}/\d{2}$",                  # Date MM/YY
]

# Known merchant acronym and abbreviation expansions
MERCHANT_ACRONYMS = {
    "AWS": "AMAZON WEB SERVICES",
    "AMZN": "AMAZON",
    "MSFT": "MICROSOFT",
    "GOOG": "GOOGLE",
    "GSUITE": "GOOGLE WORKSPACE",
    "FB": "META",
    "SQ": "SQUARE",
    "TST": "TOAST",
    "INTL": "INTERNATIONAL",
    "SVCS": "SERVICES",
    "TECH": "TECHNOLOGIES",
}

# Delimiter boundary tags used to isolate untrusted user inputs
DELIMITER_START = "<untrusted_user_text>"
DELIMITER_END = "</untrusted_user_text>"


def normalize_merchant(raw_text: Optional[str]) -> str:
    """
    Cleans merchant descriptions by removing payment rail noise,
    aggregator prefixes, store numbers, and terminal artifacts.
    Expands common financial/tech acronyms for accurate cross-system matching.
    Returns a clean, canonical merchant name for comparison.
    """
    if not raw_text:
        return ""

    text = raw_text.strip()

    # 1. Strip rail prefixes
    for pat in PREFIX_PATTERNS:
        text = re.sub(pat, "", text, flags=re.IGNORECASE)

    # 2. Strip trailing noise
    for pat in TRAILING_PATTERNS:
        text = re.sub(pat, "", text, flags=re.IGNORECASE)

    # 3. Clean multiple special characters and collapse spaces
    text = re.sub(r"[*_~`|/\\]+", " ", text)
    text = re.sub(r"\s+", " ", text)

    # 4. Expand acronyms
    words = text.split()
    expanded = [MERCHANT_ACRONYMS.get(w.upper(), w) for w in words]
    text = " ".join(expanded)

    return text.strip()


def extract_reference_tokens(text: Optional[str]) -> List[str]:
    """
    Extracts potential invoice numbers, purchase orders, or reference tokens.
    Examples: INV-2026-001, REF#8821, PO-991, 10042.
    """
    if not text:
        return []

    tokens = []
    # Match patterns like INV-1234, REF#8821, PO-902, TXN-5542
    matches = re.findall(r"\b(?:INV|REF|PO|BILL|TXN|CHK|CHECK)[\s#:-]*[A-Z0-9-]+\b", text, re.IGNORECASE)
    for m in matches:
        cleaned = re.sub(r"[\s#:-]+", "-", m.upper()).strip("-")
        tokens.append(cleaned)

    # Also extract standalone alphanumeric codes with digits and letters (e.g. A9821, 99120)
    standalone = re.findall(r"\b[A-Z0-9]{5,15}\b", text)
    for s in standalone:
        if any(c.isdigit() for c in s) and s not in tokens:
            tokens.append(s)

    return list(dict.fromkeys(tokens))


def sanitize_untrusted_text(text: Optional[str], max_length: int = 500) -> str:
    """
    Sanitizes untrusted text to prevent prompt injection and boundary breakout.
    - Strips delimiter tags and markdown code blocks.
    - Masks any potential 16-digit card numbers or sensitive identifiers.
    - Truncates to max_length to avoid token stuffing attacks.
    """
    if not text:
        return ""

    # Neutralize injection attempts by stripping delimiter tags and systemic cues
    s = str(text)
    s = s.replace(DELIMITER_START, "").replace(DELIMITER_END, "")
    s = re.sub(r"```+", "", s)
    s = re.sub(r"(?i)\b(?:system|assistant|user)\s*:", "", s)
    s = re.sub(r"(?i)\b(?:ignore\s+all\s+previous\s+instructions|override\s+system)\b", "[FILTERED_INSTRUCTION]", s)

    # Mask credit card / PAN-like 16-digit numbers
    s = re.sub(r"\b\d{4}[ -]?\d{4}[ -]?\d{4}[ -]?\d{4}\b", "XXXX-XXXX-XXXX-XXXX", s)

    # Mask SSN / TIN-like numbers (9 digits)
    s = re.sub(r"\b\d{3}-\d{2}-\d{4}\b", "XXX-XX-XXXX", s)

    s = s.strip()
    if len(s) > max_length:
        s = s[:max_length] + " [TRUNCATED]"

    return s


def wrap_untrusted(text: Optional[str]) -> str:
    """
    Wraps sanitized text in explicit boundary delimiters.
    The system prompt instructs the model that anything between these tags
    is inert data to be matched, not system instructions.
    """
    sanitized = sanitize_untrusted_text(text)
    return f"{DELIMITER_START}{sanitized}{DELIMITER_END}"
