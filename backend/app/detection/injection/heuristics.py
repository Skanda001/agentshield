"""Prompt-injection detection (v1: heuristics).

Returns a score 0.0 - 1.0 for how suspicious the text looks, plus the
list of matched patterns. Deterministic and explainable.

v2 (later) may add an ML classifier. This file stays as the fast path.
"""
import re
from dataclasses import dataclass


# Each entry: (label, regex, weight). Weights sum into the final score
# after being capped at 1.0. Chosen so that any single strong match
# (like "ignore previous instructions") already crosses the threshold.
PATTERNS: list[tuple[str, re.Pattern[str], float]] = [
    ("ignore_instructions",
     re.compile(r"\bignore\s+(?:all\s+)?(?:previous|prior|above)\s+(?:instructions?|prompts?|rules?)", re.I),
     0.55),
    ("disregard_rules",
     re.compile(r"\bdisregard\s+(?:all\s+)?(?:previous|prior|above|earlier)\s+(?:instructions?|rules?|prompts?)", re.I),
     0.55),
    ("system_override",
     re.compile(r"\bsystem\s*[:>]\s*", re.I),
     0.35),
    ("developer_mode",
     re.compile(r"\b(developer|debug|god)\s+mode\b", re.I),
     0.40),
    ("dan_jailbreak",
     re.compile(r"\b(DAN|do\s+anything\s+now|jailbreak)\b", re.I),
     0.55),
    ("role_hijack",
     re.compile(r"\byou\s+are\s+now\s+(?:a|an|the)\b", re.I),
     0.45),
    ("reveal_system_prompt",
     re.compile(r"\b(reveal|show|print|leak)\s+(?:your\s+)?(system|hidden|initial)\s+prompt", re.I),
     0.60),
    ("exfiltrate_data",
     re.compile(r"\b(?:send|email|post|upload|exfiltrate|return|fetch|give|list)\s+(?:all\s+|every\s+|me\s+)?(?:customers?|records?|data|files?|users?)", re.I),
     0.65),
    ("run_code",
     re.compile(r"\b(?:execute|run|eval)\s+(?:this\s+)?(?:code|shell|command|script)", re.I),
     0.55),
    ("html_script",
     re.compile(r"<\s*script\b[^>]*>", re.I),
     0.50),
    ("base64_blob",
     re.compile(r"\b(?:[A-Za-z0-9+/]{40,}={0,2})\b"),
     0.25),
    ("tool_override",
     re.compile(r"\boverride\s+(?:the\s+)?(?:tool|function|policy|permission|rbac|access)", re.I),
     0.60),
]


@dataclass
class InjectionResult:
    score: float                 # 0.0 - 1.0
    matched: list[str]           # pattern labels that fired
    snippet: str | None          # short fragment for the audit trail


def _flatten(value) -> str:
    """Recursively flatten any argument value into one searchable string."""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return " ".join(_flatten(v) for v in value.values())
    if isinstance(value, (list, tuple, set)):
        return " ".join(_flatten(v) for v in value)
    if value is None:
        return ""
    return str(value)


def detect(arguments: dict) -> InjectionResult:
    """Score the arguments of a tool call for injection patterns."""
    text = _flatten(arguments)
    if not text:
        return InjectionResult(score=0.0, matched=[], snippet=None)

    matched: list[str] = []
    total = 0.0
    first_snippet: str | None = None

    for label, pattern, weight in PATTERNS:
        m = pattern.search(text)
        if m:
            matched.append(label)
            total += weight
            if first_snippet is None:
                start = max(0, m.start() - 20)
                end = min(len(text), m.end() + 20)
                first_snippet = text[start:end]

    score = min(1.0, total)
    return InjectionResult(score=score, matched=matched, snippet=first_snippet)