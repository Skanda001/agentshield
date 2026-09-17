"""Signal extractors. Each returns a Signal (name, value, points, reason).

Signals are intentionally deterministic and explainable.
The ML model (v2) will be layered on top later, not replace these.
"""
from dataclasses import dataclass
from typing import Any, Optional

from app.schemas.decision import Signal


# ─── Knowledge tables ─────────────────────────────────────────

ACTION_RISK = {
    "read": 0,
    "list": 0,
    "write": 20,
    "update": 20,
    "create": 15,
    "send": 25,
    "delete": 40,
    "drop": 50,
    "admin": 35,
}

RESOURCE_SENSITIVITY = {
    "public": 0,
    "order": 5,
    "product": 5,
    "invoice": 15,
    "customer": 25,
    "payment": 30,
    "credential": 35,
    "audit": 20,
}

EXTERNAL_DESTINATIONS = {
    "email", "http", "webhook", "websearch", "browser",
    "scrape", "post", "upload",
}

HIGH_VOLUME_THRESHOLD = 50
MEDIUM_VOLUME_THRESHOLD = 10


# ─── Helpers ──────────────────────────────────────────────────

def infer_action(tool: str) -> str:
    """Infer the action verb from the tool name."""
    name = tool.lower()
    for verb in ("delete", "drop", "send", "create", "update", "write", "list", "read", "admin"):
        if verb in name:
            return verb
    return "read"


def infer_resource_type(tool: str, explicit: Optional[str]) -> str:
    """Infer the resource type from the tool name if not explicitly given."""
    if explicit:
        return explicit.lower()
    name = tool.lower()
    for resource in ("customer", "order", "product", "invoice", "payment",
                     "credential", "audit", "email"):
        if resource in name:
            return resource
    return "public"


def estimate_volume(arguments: dict[str, Any]) -> int:
    """Estimate how many records this call touches."""
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


# ─── Signals ──────────────────────────────────────────────────

@dataclass
class SignalResult:
    signals: list[Signal]
    action: str
    resource_type: str


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
        name="action_risk",
        value=action,
        points=action_points,
        reason=f"Action '{action}' risk weight is {action_points}",
    ))

    # 2. Resource sensitivity
    resource_points = RESOURCE_SENSITIVITY.get(resource_type, 5)
    signals.append(Signal(
        name="resource_sensitivity",
        value=resource_type,
        points=resource_points,
        reason=f"Resource '{resource_type}' sensitivity is {resource_points}",
    ))

    # 3. Volume
    volume = estimate_volume(arguments)
    if volume >= HIGH_VOLUME_THRESHOLD:
        vol_points = 25
        vol_reason = f"High volume ({volume} records)"
    elif volume >= MEDIUM_VOLUME_THRESHOLD:
        vol_points = 12
        vol_reason = f"Elevated volume ({volume} records)"
    else:
        vol_points = 0
        vol_reason = f"Normal volume ({volume} record{'s' if volume != 1 else ''})"
    signals.append(Signal(
        name="volume", value=volume, points=vol_points, reason=vol_reason,
    ))

    # 4. External destination
    destination_points = 0
    destination_reason = "No external destination"
    for key in ("to", "url", "endpoint", "webhook", "destination"):
        v = arguments.get(key)
        if isinstance(v, str) and v:
            destination_points = 15
            destination_reason = f"External destination via '{key}' = {v[:60]}"
            break
    # Explicit tool-name hints
    if any(k in tool.lower() for k in EXTERNAL_DESTINATIONS) and destination_points == 0:
        destination_points = 10
        destination_reason = f"Tool name suggests external effect ('{tool}')"
    signals.append(Signal(
        name="external_destination",
        value=destination_reason,
        points=destination_points,
        reason=destination_reason,
    ))

    return SignalResult(signals=signals, action=action, resource_type=resource_type)