"""Deterministic risk scoring engine (v1).

Combines signals into a 0-100 risk score, then maps the score to a verdict:
  0–29   -> ALLOW    (safe, proceed)
  30–69  -> HITL     (Human-in-the-Loop: needs human approval)
  70–100 -> BLOCK    (refused; tool body does not execute)

Thresholds are imported from app.core.constants — there is ONE source of
truth for these numbers. Do not hard-code the boundaries anywhere else.

Deterministic-first is intentional: security decisions must be explainable
and predictable. The ML layer (v2) will augment this, not replace it.
"""
from dataclasses import dataclass
from typing import Any, Optional

from app.core.constants import ALLOW_MAX, HITL_MAX, VERDICT_ALLOW, VERDICT_HITL, VERDICT_BLOCK
from app.risk_engine.signals import extract_signals
from app.schemas.decision import Signal


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
        return VERDICT_ALLOW
    if score <= HITL_MAX:
        return VERDICT_HITL
    return VERDICT_BLOCK


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