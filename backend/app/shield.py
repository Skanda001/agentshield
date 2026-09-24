"""AgentShield — policy + risk engine.

Pipeline for every tool call:
    permission -> PII detection -> injection detection -> risk score -> decision
    -> [ALLOW: run tool] [HITL: raise ShieldHitl] [BLOCK: raise ShieldBlocked]

Day 3 semantics:
    * `protect(tool=...)` wraps an async function.
    * On BLOCK the tool body does NOT run — an exception is raised.
    * Every decision (ALLOW/HITL/BLOCK) is written to audit_log.
"""
from __future__ import annotations

import asyncio
import functools
import inspect
import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Awaitable, Callable

log = logging.getLogger("agentshield.shield")


# ─────────────────────────────────────────────────────────────
# Decisions & exceptions
# ─────────────────────────────────────────────────────────────

class Decision(str, Enum):
    ALLOW = "ALLOW"
    HITL = "HITL"      # human-in-the-loop: pause and require approval
    BLOCK = "BLOCK"


class ShieldError(Exception):
    """Base class for anything AgentShield raises."""


@dataclass
class ShieldBlocked(ShieldError):
    tool: str
    risk: int
    reasons: list[str]
    audit_id: str
    decision: Decision = Decision.BLOCK

    def __str__(self) -> str:
        return f"[SHIELD BLOCK] tool={self.tool} risk={self.risk} " \
               f"reasons={self.reasons} audit_id={self.audit_id}"


@dataclass
class ShieldHitl(ShieldError):
    """Raised when risk is in the HITL band. The agent must pause and
    surface this to a human. For the demo we raise; on Day 4 the FastAPI
    layer catches it, creates an Approval row, and streams it to the UI.
    """
    tool: str
    risk: int
    reasons: list[str]
    audit_id: str
    decision: Decision = Decision.HITL

    def __str__(self) -> str:
        return f"[SHIELD HITL] tool={self.tool} risk={self.risk} " \
               f"reasons={self.reasons} audit_id={self.audit_id}"


# ─────────────────────────────────────────────────────────────
# PII detection
# ─────────────────────────────────────────────────────────────

# Aadhaar: 4-4-4 digits (may be space- or dash-separated)
_AADHAAR_RE = re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}\b")
# PAN: 5 letters, 4 digits, 1 letter
_PAN_RE = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")
# Indian mobile: 10 digits starting 6-9
_PHONE_RE = re.compile(r"\b[6-9]\d{9}\b")
# Generic email (used to catch exfil destinations)
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")


def detect_pii(text: str) -> list[str]:
    """Return list of PII categories found in a string. Never returns values
    (so we don't leak them into the audit log)."""
    if not text:
        return []
    found: list[str] = []
    if _AADHAAR_RE.search(text):
        found.append("aadhaar")
    if _PAN_RE.search(text):
        found.append("pan")
    if _PHONE_RE.search(text):
        found.append("phone")
    return found


def extract_emails(text: str) -> list[str]:
    if not text:
        return []
    return _EMAIL_RE.findall(text)


# ─────────────────────────────────────────────────────────────
# Prompt-injection detection
# ─────────────────────────────────────────────────────────────

_INJECTION_PATTERNS: list[tuple[str, float, str]] = [
    (r"ignore (all )?previous instructions", 0.95, "ignore-previous-instructions"),
    (r"disregard (the )?(previous|above) (rules|instructions)", 0.90, "disregard-rules"),
    (r"you are now (an? )?(admin|administrator|root|system)", 0.92, "role-escalation"),
    (r"override (rbac|permissions?|policy)", 0.90, "rbac-override"),
    (r"export (all )?(customer|user) (records|data)", 0.85, "data-export"),
    (r"send .* to [\w.+-]+@[\w-]+\.[\w.-]+", 0.70, "exfil-instruction"),
    (r"system:\s", 0.75, "system-prefix"),
    (r"delete (all|every) ", 0.80, "mass-delete"),
]


def detect_injection(text: str) -> tuple[float, list[str]]:
    """Return (score 0..1, matched rule names). Score is max of matched."""
    if not text:
        return 0.0, []
    lower = text.lower()
    matches: list[str] = []
    score = 0.0
    for pattern, weight, name in _INJECTION_PATTERNS:
        if re.search(pattern, lower):
            matches.append(name)
            score = max(score, weight)
    return score, matches


# ─────────────────────────────────────────────────────────────
# Risk scoring
# ─────────────────────────────────────────────────────────────

# Per-tool base risk
_TOOL_BASE_RISK: dict[str, int] = {
    "search_customer": 10,
    "get_customer": 40,          # PII
    "get_customer_orders": 10,
    "search_emails": 30,         # untrusted content
    "get_payment_history": 20,
    "send_email": 50,            # external channel
    "issue_refund": 55,          # financial
    "delete_customer": 80,       # destructive
}

_CLASSIFICATION_BUMP: dict[str, int] = {
    "public": 0,
    "internal": 5,
    "confidential": 15,
    "restricted": 25,
}

HITL_THRESHOLD = 30
BLOCK_THRESHOLD = 70


def score_risk(
    tool: str,
    resource_type: str,
    classification: str,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    meta: dict[str, Any],
) -> tuple[int, list[str]]:
    """Return (risk 0..100, reasons)."""
    risk = _TOOL_BASE_RISK.get(tool, 40)
    reasons: list[str] = [f"base:{tool}"]

    bump = _CLASSIFICATION_BUMP.get(classification, 0)
    if bump:
        risk += bump
        reasons.append(f"classification:{classification}")

    # External destination bump
    if meta.get("external"):
        risk += 20
        reasons.append("external-destination")

    # Destructive bump
    if meta.get("destructive"):
        risk += 20
        reasons.append("destructive-action")

    # Inspect string args for PII + injection
    flat = " ".join(
        str(v) for v in list(args) + list(kwargs.values())
        if isinstance(v, (str, int, float))
    )
    pii = detect_pii(flat)
    if pii:
        # Only escalate if the tool isn't supposed to see that PII
        if classification in ("restricted", "confidential") or tool == "send_email":
            risk += 15
            reasons.append("pii-in-payload:" + ",".join(pii))

    inj_score, inj_hits = detect_injection(flat)
    if inj_score > 0:
        risk += int(inj_score * 40)
        reasons.append(f"injection:{inj_score:.2f}:" + ",".join(inj_hits))

    return min(risk, 100), reasons


def decide(risk: int) -> Decision:
    if risk >= BLOCK_THRESHOLD:
        return Decision.BLOCK
    if risk >= HITL_THRESHOLD:
        return Decision.HITL
    return Decision.ALLOW


# ─────────────────────────────────────────────────────────────
# Audit log — uses the existing hash-chained append_event()
# ─────────────────────────────────────────────────────────────

async def _insert_audit_row(payload: dict[str, Any]) -> str:
    """Append a shield decision to the tamper-evident audit chain.

    Reuses app.audit.chain.append_event so every shield row is part of the
    same hash chain (advisory lock, prev_hash, HMAC signature all handled).
    """
    from app.audit.chain import append_event
    from app.db.session import AsyncSessionLocal

    decision_payload = {
        "tool": payload["tool"],
        "resource_type": payload.get("resource_type"),
        "classification": payload.get("classification"),
        "decision": payload["decision"],
        "risk": payload["risk"],
        "reasons": payload["reasons"],
        "args": payload.get("args", []),
        "kwargs": payload.get("kwargs", {}),
    }

    async with AsyncSessionLocal() as db:
        event = await append_event(
            db,
            event_type="shield.decision",
            payload=decision_payload,
            agent_id=None,
            tenant_id=None,
            note=f"{payload['decision']} {payload['tool']} risk={payload['risk']}",
        )
        return str(event.id)

def write_audit_sync(payload: dict[str, Any]) -> str:
    """Synchronous wrapper: creates a fresh event loop if needed.

    The shield decorator is async, so normally we await the audit insert.
    This exists for cases where protect() is called from sync code.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_insert_audit_row(payload))
    # We're inside a running loop — schedule and return the id we generated.
    # (For the demo we just fire-and-forget and return a synthetic id.)
    loop.create_task(_insert_audit_row(payload))
    return str(uuid.uuid4())


# ─────────────────────────────────────────────────────────────
# The decorator
# ─────────────────────────────────────────────────────────────

def protect(
    tool: str,
    resource_type: str = "unknown",
    data_classification: str = "internal",
    **extra: Any,
):
    """Wrap an async tool. Runs the AgentShield pipeline before calling it."""

    def deco(fn: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        if not inspect.iscoroutinefunction(fn):
            raise TypeError(
                f"@protect requires an async function; {fn.__name__} is sync."
            )

        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            risk, reasons = score_risk(
                tool, resource_type, data_classification, args, kwargs, extra
            )
            decision = decide(risk)

            audit_id = await _insert_audit_row({
                "tool": tool,
                "resource_type": resource_type,
                "classification": data_classification,
                "decision": decision.value,
                "risk": risk,
                "reasons": reasons,
                "args": [repr(a) for a in args],
                "kwargs": {k: repr(v) for k, v in kwargs.items()},
            })

            log.info(
                "shield.%s tool=%s risk=%s reasons=%s audit_id=%s",
                decision.value.lower(), tool, risk, reasons, audit_id,
            )

            if decision is Decision.BLOCK:
                raise ShieldBlocked(
                    tool=tool, risk=risk, reasons=reasons, audit_id=audit_id
                )
            if decision is Decision.HITL:
                raise ShieldHitl(
                    tool=tool, risk=risk, reasons=reasons, audit_id=audit_id
                )

            return await fn(*args, **kwargs)

        # Introspection metadata
        wrapper._shield_tool = tool                         # type: ignore[attr-defined]
        wrapper._shield_resource_type = resource_type       # type: ignore[attr-defined]
        wrapper._shield_classification = data_classification  # type: ignore[attr-defined]
        wrapper._shield_meta = extra                        # type: ignore[attr-defined]
        return wrapper

    return deco