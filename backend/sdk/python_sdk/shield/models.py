"""Data models returned by the AgentShield API."""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Signal:
    name: str
    value: Any
    points: float
    reason: str


@dataclass
class Decision:
    decision_id: str
    verdict: str           # ALLOW | BLOCK | ESCALATE
    risk_score: float
    tool: str
    action: str
    reasons: list[str] = field(default_factory=list)
    signals: list[Signal] = field(default_factory=list)
    policy_rule: str | None = None
    policy_effect: str | None = None
    injection_score: float = 0.0
    pii_classification: str | None = None
    pii_labels: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Decision":
        signals = [Signal(**s) for s in d.get("signals", [])]
        return cls(
            decision_id=str(d["decision_id"]),
            verdict=d["verdict"],
            risk_score=float(d["risk_score"]),
            tool=d["tool"],
            action=d["action"],
            reasons=list(d.get("reasons", [])),
            signals=signals,
            policy_rule=d.get("policy_rule"),
            policy_effect=d.get("policy_effect"),
            injection_score=float(d.get("injection_score", 0.0)),
            pii_classification=d.get("pii_classification"),
            pii_labels=list(d.get("pii_labels", [])),
        )