"""Signal extractors. Each returns a Signal (name, value, points, reason).

Signals are deterministic and explainable.
ML models (v2) will be layered on top later, not replace these.
"""
from dataclasses import dataclass, field
from typing import Any, Optional

from app.detection.injection.heuristics import detect as detect_injection
from app.detection.pii.presidio_wrapper import detect as detect_pii
from app.schemas.decision import Signal


# ─── Knowledge tables ─────────────────────────────────────────

ACTION_RISK = {
    "read": 0, "list": 0,
    "write": 20, "update": 20, "create": 15,
    "send": 25, "delete": 40, "drop": 50, "admin": 35,
}

RESOURCE_SENSITIVITY = {
    "public": 0, "order": 5, "product": 5,
    "invoice": 15, "customer": 25, "payment": 30,
    "credential": 35, "audit": 20,
}

EXTERNAL_DESTINATIONS = {
    "email", "http", "webhook", "websearch", "browser",
    "scrape", "post", "upload",
}

HIGH_VOLUME_THRESHOLD = 50
MEDIUM_VOLUME_THRESHOLD = 10

INJECTION_LOW = 0.30
INJECTION_MEDIUM = 0.60
INJECTION_HIGH = 0.80

# PII classification -> extra points when the call also has an external effect
PII_EXTERNAL_BONUS = {
    "public": 0,
    "internal": 5,
    "confidential": 15,
    "restricted": 30,
}


# ─── Helpers ──────────────────────────────────────────────────

def infer_action(tool: str) -> str:
    name = tool.lower()
    for verb in ("delete", "drop", "send", "create", "update", "write", "list", "read", "admin"):
        if verb in name:
            return verb
    return "read"


def infer_resource_type(tool: str, explicit: Optional[str]) -> str:
    if explicit:
        return explicit.lower()
    name = tool.lower()
    for resource in ("customer", "order", "product", "invoice", "payment",
                     "credential", "audit", "email"):
        if resource in name:
            return resource
    return "public"


def estimate_volume(arguments: dict[str, Any]) -> int:
    for key in ("count", "limit", "max_results", "page_size"):
        v = arguments.get(key)
        if isinstance(v, int):
            return v
    ids = arguments.get("ids") or arguments.get("customer_ids")
    if isinstance(ids, list):
        return len(ids)
    if "all" in arguments and arguments["all"] is True:
        return HIGH_VOLUME_THRESHOLD * 10
    return 1


# ─── Result container ─────────────────────────────────────────

@dataclass
class SignalResult:
    signals: list[Signal] = field(default_factory=list)
    action: str = "read"
    resource_type: str = "public"
    injection_score: float = 0.0
    pii_classification: str = "public"
    pii_labels: list[str] = field(default_factory=list)


# ─── Main extractor ───────────────────────────────────────────

def extract_signals(
    *,
    tool: str,
    arguments: dict[str, Any],
    resource_type_explicit: Optional[str] = None,
) -> SignalResult:
    signals: list[Signal] = []

    action = infer_action(tool)
    resource_type = infer_resource_type(tool, resource_type_explicit)

    # 1. Action risk
    action_points = ACTION_RISK.get(action, 10)
    signals.append(Signal(
        name="action_risk", value=action, points=action_points,
        reason=f"Action '{action}' risk weight is {action_points}",
    ))

    # 2. Resource sensitivity
    resource_points = RESOURCE_SENSITIVITY.get(resource_type, 5)
    signals.append(Signal(
        name="resource_sensitivity", value=resource_type, points=resource_points,
        reason=f"Resource '{resource_type}' sensitivity is {resource_points}",
    ))

    # 3. Volume
    volume = estimate_volume(arguments)
    if volume >= HIGH_VOLUME_THRESHOLD:
        vol_points, vol_reason = 25, f"High volume ({volume} records)"
    elif volume >= MEDIUM_VOLUME_THRESHOLD:
        vol_points, vol_reason = 12, f"Elevated volume ({volume} records)"
    else:
        vol_points = 0
        vol_reason = f"Normal volume ({volume} record{'s' if volume != 1 else ''})"
    signals.append(Signal(name="volume", value=volume, points=vol_points, reason=vol_reason))

    # 4. External destination
    destination_points = 0
    destination_reason = "No external destination"
    for key in ("to", "url", "endpoint", "webhook", "destination"):
        v = arguments.get(key)
        if isinstance(v, str) and v:
            destination_points = 15
            destination_reason = f"External destination via '{key}' = {v[:60]}"
            break
    if any(k in tool.lower() for k in EXTERNAL_DESTINATIONS) and destination_points == 0:
        destination_points = 10
        destination_reason = f"Tool name suggests external effect ('{tool}')"
    signals.append(Signal(
        name="external_destination", value=destination_reason,
        points=destination_points, reason=destination_reason,
    ))

    # 5. Prompt injection
    inj = detect_injection(arguments)
    if inj.score >= INJECTION_HIGH:
        inj_points = 45
    elif inj.score >= INJECTION_MEDIUM:
        inj_points = 30
    elif inj.score >= INJECTION_LOW:
        inj_points = 15
    else:
        inj_points = 0
    if inj_points > 0:
        detail = ", ".join(inj.matched[:3]) or "pattern match"
        signals.append(Signal(
            name="prompt_injection", value=inj.score, points=inj_points,
            reason=f"Prompt injection detected (score {inj.score:.2f}): {detail}",
        ))
    else:
        signals.append(Signal(
            name="prompt_injection", value=inj.score, points=0,
            reason="No injection patterns detected",
        ))

    # 6. PII / data classification
    pii = detect_pii(arguments)
    pii_points = 0
    pii_reason = "No PII detected"

    # Base points from PII sensitivity
    pii_points += pii.total_points

    # Extra points when PII + external effect (potential exfiltration)
    if destination_points > 0 and pii.highest_classification != "public":
        bonus = PII_EXTERNAL_BONUS.get(pii.highest_classification, 0)
        pii_points += bonus
        pii_reason = (
            f"{pii.highest_classification} PII detected and call has external effect "
            f"(+{pii.total_points} +{bonus} bonus)"
        )
    elif pii.matches:
        labels = ", ".join(pii.summary[:4])
        pii_reason = f"PII detected ({len(pii.matches)} matches): {labels}"
    else:
        pii_reason = "No PII detected"

    signals.append(Signal(
        name="pii",
        value=pii.highest_classification,
        points=pii_points,
        reason=pii_reason,
    ))

    return SignalResult(
        signals=signals,
        action=action,
        resource_type=resource_type,
        injection_score=inj.score,
        pii_classification=pii.highest_classification,
        pii_labels=[m.label for m in pii.matches],
    )