"""In-flight PII Redaction and Masking engine for AgentShield.

Recursively redacts sensitive PII (PAN, Aadhaar, credit cards, emails, phones, IBAN)
from strings, dictionaries, lists, and tool arguments before execution.
"""
from __future__ import annotations

import re
from typing import Any

# Recognizers ordered by length to prevent partial subset collisions:
# (Credit Card 16 digits -> Aadhaar 12 digits -> Phone 10 digits)
_CREDIT_CARD_RE = re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b|\b\d{16}\b")
_AADHAAR_RE = re.compile(r"(?<!\d)[2-9]\d{3}\s\d{4}\s\d{4}(?!\d)")
_PAN_RE = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")
_EMAIL_RE = re.compile(r"\b([A-Za-z0-9._%+-])[A-Za-z0-9._%+-]*(@[A-Za-z0-9.-]+\.[A-Za-z]{2,})\b")
_PHONE_RE = re.compile(r"(?<!\d)(?:\+91[\s-]?)?[6-9]\d{9}(?!\d)")
_PASSPORT_RE = re.compile(r"\b[A-PR-WY][1-9]\d{0,2}\s?\d{4}\b")
_IBAN_RE = re.compile(r"\b([A-Z]{2}\d{2})[A-Z0-9]{11,30}\b")


def mask_string(val: str) -> tuple[str, list[str]]:
    """Mask sensitive patterns in a string and return (masked_string, list_of_labels)."""
    if not val or not isinstance(val, str):
        return val, []

    labels: list[str] = []
    result = val

    # 1. Mask Credit Cards (16 digits) FIRST to avoid Aadhaar (12 digits) partial collision
    if _CREDIT_CARD_RE.search(result):
        def _mask_cc(m: re.Match) -> str:
            raw = m.group(0)
            clean = re.sub(r"[ -]", "", raw)
            if len(clean) == 16:
                if " " in raw:
                    parts = raw.split(" ")
                    if len(parts) == 4:
                        return f"{parts[0]} **** **** {parts[3]}"
                return clean[:4] + " **** **** " + clean[-4:]
            return clean[:4] + " **** " + clean[-4:]
        result = _CREDIT_CARD_RE.sub(_mask_cc, result)
        labels.append("credit_card")

    # 2. Mask Aadhaar (12 digits, 4-4-4)
    if _AADHAAR_RE.search(result):
        def _mask_aadhaar(m: re.Match) -> str:
            raw = m.group(0)
            parts = raw.split()
            if len(parts) == 3:
                return f"{parts[0]} **** {parts[2]}"
            return raw[:4] + " **** " + raw[-4:]
        result = _AADHAAR_RE.sub(_mask_aadhaar, result)
        labels.append("aadhaar")

    # 3. Mask PAN: ABCDE1234F -> ABCDE****F
    if _PAN_RE.search(result):
        def _mask_pan(m: re.Match) -> str:
            pan = m.group(0)
            return pan[:5] + "****" + pan[-1]
        result = _PAN_RE.sub(_mask_pan, result)
        labels.append("pan")

    # 4. Mask Email: alice.smith@example.com -> a***@example.com
    if _EMAIL_RE.search(result):
        def _mask_email(m: re.Match) -> str:
            first_char = m.group(1)
            domain = m.group(2)
            return f"{first_char}***{domain}"
        result = _EMAIL_RE.sub(_mask_email, result)
        labels.append("email")

    # 5. Mask Phone: +919876543210 -> +91 **** 3210 or 9876543210 -> ****3210
    if _PHONE_RE.search(result):
        def _mask_phone(m: re.Match) -> str:
            raw = m.group(0)
            if raw.startswith("+91"):
                return "+91 **** " + raw[-4:]
            return "****" + raw[-4:]
        result = _PHONE_RE.sub(_mask_phone, result)
        labels.append("phone")

    # 6. Mask Passport
    if _PASSPORT_RE.search(result):
        def _mask_passport(m: re.Match) -> str:
            raw = m.group(0)
            return raw[:2] + "****" + raw[-2:]
        result = _PASSPORT_RE.sub(_mask_passport, result)
        labels.append("passport")

    return result, list(set(labels))


def mask_pii_in_data(data: Any) -> tuple[Any, list[str]]:
    """Recursively mask PII in strings, dicts, lists, and tuples."""
    if isinstance(data, str):
        return mask_string(data)

    if isinstance(data, dict):
        masked_dict = {}
        all_labels = []
        for k, v in data.items():
            mv, labels = mask_pii_in_data(v)
            masked_dict[k] = mv
            all_labels.extend(labels)
        return masked_dict, list(set(all_labels))

    if isinstance(data, list):
        masked_list = []
        all_labels = []
        for item in data:
            mv, labels = mask_pii_in_data(item)
            masked_list.append(mv)
            all_labels.extend(labels)
        return masked_list, list(set(all_labels))

    if isinstance(data, tuple):
        masked_list = []
        all_labels = []
        for item in data:
            mv, labels = mask_pii_in_data(item)
            masked_list.append(mv)
            all_labels.extend(labels)
        return tuple(masked_list), list(set(all_labels))

    return data, []
