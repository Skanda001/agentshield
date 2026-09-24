"""AgentShield decorator — Day 2 STUB.

This is intentionally minimal. It logs every tool call and passes through.
Day 3 replaces the body of `wrapper` with the real pipeline:
    permission check → PII detection → injection detection → risk scoring → HITL/BLOCK

The public surface (`protect(tool=..., resource_type=..., **meta)`) will NOT
change when the real engine lands, so every tool written today keeps working.
"""
from __future__ import annotations

import functools
import logging
from typing import Any, Awaitable, Callable

log = logging.getLogger("agentshield.shield")


def protect(
    tool: str,
    resource_type: str = "unknown",
    data_classification: str = "internal",
    **extra: Any,
):
    """Decorate an async tool function.

    Args:
        tool: canonical tool name, e.g. "send_email".
        resource_type: "customer" | "order" | "email" | "payment".
        data_classification: "public" | "internal" | "confidential" | "restricted".
        **extra: reserved for future policy metadata (e.g. external=True).
    """

    def deco(fn: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # ── Day 2: pass-through with logging ──────────────────
            log.info(
                "shield.allow tool=%s resource=%s classification=%s args=%s kwargs=%s",
                tool, resource_type, data_classification, args, kwargs,
            )
            return await fn(*args, **kwargs)

        # Metadata LangGraph / introspection can read
        wrapper._shield_tool = tool                    # type: ignore[attr-defined]
        wrapper._shield_resource_type = resource_type  # type: ignore[attr-defined]
        wrapper._shield_classification = data_classification  # type: ignore[attr-defined]
        wrapper._shield_meta = extra                   # type: ignore[attr-defined]
        return wrapper

    return deco