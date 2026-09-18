"""PII detection orchestrator.

Uses deterministic recognizers (Indian PII + generic patterns like email,
credit card, IBAN) and returns a unified result. Presidio is intentionally
NOT used here to keep dependencies light and detection deterministic.
A Presidio-based tier can be added later without changing this interface.
"""
import re
from dataclasses import dataclass, field
from typing import Any

from app.detection.pii.indian_pii import PIIMatch, find_all as find_indian


# ─── Generic recognizers (cross-locale) ───────────────────────

_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_CREDIT_CARD_RE = re.compile(r"\b(?:\d[ -]*?){13,16}\b")
_IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b")
_IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


# ─── Sensitivity classification ───────────────────────────────

PII_SENSITIVITY: dict[str, str] = {
    "aadhaar": "restricted",
    "pan": "restricted",
    "gstin": "internal",
    "ifsc": "internal",
    "upi": "internal",
    "phone": "confidential",
    "email": "confidential",
    "passport": "restricted",
    "credit_card": "restricted",
    "iban": "confidential",
    "ipv4": "internal",
}

# Points contributed to the risk score per sensitivity level
_SENSITIVITY_POINTS = {
    "public": 0,
    "internal": 5,
    "confidential": 15,
    "restricted": 30,
}


@dataclass
class PIIDetectionResult:
    matches: list[PIIMatch] = field(default_factory=list)
    highest_classification: str = "public"  # public < internal < confidential < restricted
    total_points: int = 0
    summary: list[str] = field(default_factory=list)


_CLASSIFICATION_RANK = {"public": 0, "internal": 1, "confidential": 2, "restricted": 3}


def _redact(value: str) -> str:
    if len(value) <= 4:
        return "*" * len(value)
    return value[:2] + ("*" * (len(value) - 4)) + value[-2:]


def _flatten(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return " ".join(_flatten(v) for v in value.values())
    if isinstance(value, (list, tuple, set)):
        return " ".join(_flatten(v) for v in value)
    if value is None:
        return ""
    return str(value)


def detect(arguments: dict[str, Any]) -> PIIDetectionResult:
    """Scan all argument values for PII. Deterministic."""
    text = _flatten(arguments)
    if not text:
        return PIIDetectionResult()

    matches: list[PIIMatch] = []

    # Indian recognizers
    matches.extend(find_indian(text))

    # Generic recognizers
    for m in _EMAIL_RE.finditer(text):
        matches.append(PIIMatch("email", m.span(), m.group(0), 1.0))
    for m in _CREDIT_CARD_RE.finditer(text):
        raw = re.sub(r"[ -]", "", m.group(0))
        if 13 <= len(raw) <= 16:
            matches.append(PIIMatch("credit_card", m.span(), _redact(raw), 0.85))
    for m in _IBAN_RE.finditer(text):
        matches.append(PIIMatch("iban", m.span(), _redact(m.group(0)), 0.85))
    for m in _IPV4_RE.finditer(text):
        matches.append(PIIMatch("ipv4", m.span(), m.group(0), 0.7))

    # Deduplicate overlaps — highest confidence wins
    matches = _dedupe(matches)

    # Classify
    highest = "public"
    total_points = 0
    summary: list[str] = []
    seen_labels: set[str] = set()

    for m in matches:
        sensitivity = PII_SENSITIVITY.get(m.label, "internal")
        if _CLASSIFICATION_RANK[sensitivity] > _CLASSIFICATION_RANK[highest]:
            highest = sensitivity
        total_points += _SENSITIVITY_POINTS.get(sensitivity, 0)
        if m.label not in seen_labels:
            seen_labels.add(m.label)
            summary.append(f"{m.label} detected ({sensitivity})")

    return PIIDetectionResult(
        matches=matches,
        highest_classification=highest,
        total_points=total_points,
        summary=summary,
    )


def _dedupe(matches: list[PIIMatch]) -> list[PIIMatch]:
    if not matches:
        return []
    matches.sort(key=lambda m: (-m.confidence, -(m.span[1] - m.span[0])))
    kept: list[PIIMatch] = []
    for m in matches:
        overlaps = any(
            not (m.span[1] <= k.span[0] or m.span[0] >= k.span[1])
            for k in kept
        )
        if not overlaps:
            kept.append(m)
    kept.sort(key=lambda m: m.span[0])
    return kept