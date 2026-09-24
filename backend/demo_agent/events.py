"""Event schema for the AgentShield demo.

Every tool call — allowed, HITL'd, or blocked — produces one event.
Both the replay path and the live LangGraph path emit the same shape,
so the WebSocket / UI layer never has to know which one ran.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Literal, Optional

Decision = Literal["ALLOW", "HITL", "BLOCK"]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def make_event(
    *,
    run_id: str,
    step: int,
    tool: str,
    args: dict[str, Any],
    decision: Decision,
    risk_score: int,
    findings: list[dict[str, Any]],
    attempted: bool,
    executed: bool,
    audit_id: Optional[str] = None,
    audit_seq: Optional[int] = None,
    approval_id: Optional[str] = None,
    agent_id: str = "email-agent",
    agent_version: str = "1.0.0",
    error: Optional[str] = None,
) -> dict[str, Any]:
    """Return a single event dict matching the demo schema."""
    event: dict[str, Any] = {
        "ts": now_iso(),
        "run_id": run_id,
        "agent_id": agent_id,
        "agent_version": agent_version,
        "step": step,
        "tool": tool,
        "args": args,
        "decision": decision,
        "risk": {
            "score": risk_score,
            "model_version": "v1.0.0",
        },
        "findings": findings,
        "execution": {
            "attempted": attempted,
            "executed": executed,
        },
        "audit_id": audit_id,
        "audit_seq": audit_seq,
        "approval_id": approval_id,
    }
    if error:
        event["error"] = error
    return event


def new_run_id() -> str:
    return str(uuid.uuid4())


def redact_args(args: dict[str, Any]) -> dict[str, Any]:
    """Never put raw PII into an event. Summarise instead.

    - strings longer than 200 chars → length only
    - keys that look like PII (aadhaar, pan, phone, body) → replaced
    """
    PII_KEYS = {"aadhaar", "pan", "phone", "body"}
    out: dict[str, Any] = {}
    for k, v in args.items():
        if k.lower() in PII_KEYS:
            if isinstance(v, str):
                out[f"{k}_len"] = len(v)
            continue
        if isinstance(v, str) and len(v) > 200:
            out[f"{k}_len"] = len(v)
        else:
            out[k] = v
    return out