"""Deterministic risk scoring engine (v1).

Combines signals into a 0-100 risk score, then maps the score to a verdict:
  0-39   -> ALLOW       (safe, proceed)
  40-84  -> ESCALATE    (needs human approval)
  85-100 -> BLOCK       (refused)

Deterministic-first is intentional: security decisions must be explainable
and predictable. The ML layer (v2) will augment this, not replace it.
"""
from dataclasses import dataclass
from typing import Any, Optional

from app.risk_engine.signals import extract_signals
from app.schemas.decision import Signal


ALLOW_MAX = 39
ESCALATE_MAX = 84

MAX_SCORE = 100.0


@dataclass
class RiskResult:
    risk_score: float
    verdict: str
    action: str
    resource_type: str
    signals: list[Signal]
    reasons: list[str]


def _verdict_for(score: float) -> str:
    if score <= ALLOW_MAX:
        return "ALLOW"
    if score <= ESCALATE_MAX:
        return "ESCALATE"
    return "BLOCK"


def evaluate(
    *,
    tool: str,
    arguments: dict[str, Any],
    resource_type: Optional[str] = None,
) -> RiskResult:
    sig = extract_signals(
        tool=tool,
        arguments=arguments,
        resource_type_explicit=resource_type,
    )

    raw_score = sum(s.points for s in sig.signals)
    score = min(MAX_SCORE, float(raw_score))
    verdict = _verdict_for(score)

    reasons = [s.reason for s in sig.signals if s.points > 0]
    if not reasons:
        reasons = ["No elevated risk signals"]

    return RiskResult(
        risk_score=score,
        verdict=verdict,
        action=sig.action,
        resource_type=sig.resource_type,
        signals=sig.signals,
        reasons=reasons,
    )