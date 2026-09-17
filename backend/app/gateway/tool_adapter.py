"""Tool adapter. Normalizes a tool call before it reaches the decision pipeline.

This is where per-invocation control happens (arguments, destination, volume).
It does NOT execute tools; it only prepares a normalized view.
"""
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ToolCall:
    tool: str
    arguments: dict[str, Any]
    resource_type: Optional[str] = None


@dataclass
class NormalizedCall:
    tool: str
    arguments: dict[str, Any]
    resource_type: Optional[str]
    warnings: list[str] = field(default_factory=list)


# Arguments we refuse outright (defensive baseline before the risk engine runs).
FORBIDDEN_ARG_KEYS = {"__proto__", "constructor", "prototype"}


def normalize(call: ToolCall) -> NormalizedCall:
    warnings: list[str] = []

    # Deep-ish safety: strip obviously dangerous keys
    clean_args = {k: v for k, v in call.arguments.items() if k not in FORBIDDEN_ARG_KEYS}
    if len(clean_args) != len(call.arguments):
        warnings.append("Stripped reserved argument keys")

    # Refuse non-string tool names
    if not isinstance(call.tool, str) or not call.tool.strip():
        raise ValueError("tool must be a non-empty string")

    return NormalizedCall(
        tool=call.tool.strip(),
        arguments=clean_args,
        resource_type=call.resource_type,
        warnings=warnings,
    )