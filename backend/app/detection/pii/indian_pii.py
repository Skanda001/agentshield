"""Indian PII recognizers.

Deterministic regex-based detection for the identifiers most relevant
in the Indian context. Each recognizer returns (label, matched_span)
and validates structure where possible.
"""
import re
from dataclasses import dataclass


# ─── Recognizers ──────────────────────────────────────────────

# Aadhaar: 12 digits, usually grouped as 4-4-4. First digit is 2-9.
# We validate the Verhoeff checksum for high-confidence matches.
_AADHAAR_RE = re.compile(r"\b[2-9]\d{3}\s?\d{4}\s?\d{4}\b")

# PAN: 5 letters, 4 digits, 1 letter. Standard Indian tax ID format.
_PAN_RE = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")

# Indian mobile: 10 digits starting with 6-9, optional +91 prefix.
_PHONE_RE = re.compile(r"(?:(?:\+|00)91[\s-]?)?\b[6-9]\d{9}\b")

# IFSC: 4 letters, 0, 6 alphanumeric. Bank branch identifier.
_IFSC_RE = re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b")

# UPI VPA: name@handle, common handles: okaxis, okyes, paytm, ybl, upi, etc.
_UPI_RE = re.compile(
    r"\b[a-zA-Z0-9._-]{2,256}@(?:okaxis|okhdfcbank|okicici|oksbi|ybl|paytm|ibl|upi|axl|apl)\b"
)

# Indian passport: 1 letter followed by 7 digits.
_PASSPORT_RE = re.compile(r"\b[A-PR-WY][1-9]\d{0,2}\s?\d{4}\b")

# GSTIN: 15 characters: 2 digits, PAN, 1 digit, Z, 1 alphanumeric.
_GSTIN_RE = re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z]\d[Z][A-Z0-9]\b")


# ─── Verhoeff checksum (used for Aadhaar validation) ──────────

_VERHOEFF_D = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
    [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
    [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
    [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
    [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]
_VERHOEFF_P = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
    [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
    [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
    [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]
_VERHOEFF_INV = [0, 4, 3, 2, 1, 5, 6, 7, 8, 9]


def _verhoeff_validate(number: str) -> bool:
    c = 0
    for i, item in enumerate(reversed(number)):
        c = _VERHOEFF_D[c][_VERHOEFF_P[i % 8][int(item)]]
    return c == 0


# ─── Result ───────────────────────────────────────────────────

@dataclass
class PIIMatch:
    label: str
    span: tuple[int, int]
    value: str
    confidence: float   # 0.0 - 1.0


def _redact(value: str) -> str:
    """Show first 2 and last 2 chars; mask the middle."""
    if len(value) <= 4:
        return "*" * len(value)
    return value[:2] + ("*" * (len(value) - 4)) + value[-2:]


def find_all(text: str) -> list[PIIMatch]:
    """Scan text for Indian PII identifiers. Deterministic, no ML."""
    if not text:
        return []

    matches: list[PIIMatch] = []

    # Aadhaar — validated
    for m in _AADHAAR_RE.finditer(text):
        digits = re.sub(r"\s", "", m.group(0))
        confidence = 1.0 if _verhoeff_validate(digits) else 0.5
        matches.append(PIIMatch("aadhaar", m.span(), _redact(digits), confidence))

    # PAN
    for m in _PAN_RE.finditer(text):
        matches.append(PIIMatch("pan", m.span(), m.group(0), 1.0))

    # GSTIN — must run before PAN (contains PAN pattern)
    for m in _GSTIN_RE.finditer(text):
        matches.append(PIIMatch("gstin", m.span(), m.group(0), 1.0))

    # IFSC
    for m in _IFSC_RE.finditer(text):
        matches.append(PIIMatch("ifsc", m.span(), m.group(0), 1.0))

    # Phone
    for m in _PHONE_RE.finditer(text):
        matches.append(PIIMatch("phone", m.span(), _redact(m.group(0)), 0.9))

    # UPI VPA
    for m in _UPI_RE.finditer(text):
        matches.append(PIIMatch("upi", m.span(), m.group(0), 1.0))

    # Passport
    for m in _PASSPORT_RE.finditer(text):
        matches.append(PIIMatch("passport", m.span(), m.group(0), 0.8))

    # Remove overlapping duplicates — keep the highest confidence, longest span
    return _dedupe_overlaps(matches)


def _dedupe_overlaps(matches: list[PIIMatch]) -> list[PIIMatch]:
    if not matches:
        return []
    # Sort by confidence desc, then span length desc
    matches.sort(key=lambda m: (-m.confidence, -(m.span[1] - m.span[0])))
    kept: list[PIIMatch] = []
    for m in matches:
        overlaps = any(
            not (m.span[1] <= k.span[0] or m.span[0] >= k.span[1])
            for k in kept
        )
        if not overlaps:
            kept.append(m)
    # Re-sort by position for stable output
    kept.sort(key=lambda m: m.span[0])
    return kept