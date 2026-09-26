"""Agent Package: Decoupled AI Agents Protected by AgentShield.

Usage:
    import agent

    # 1. Quick run (default support agent)
    res = agent.run("what is the adhar details of customer 1008")
    print(res.text)

    # 2. Pluggable multi-agent testing
    support = agent.get_agent("support")
    res1 = support.run("Check recent orders for customer 1001")

    finance = agent.get_agent("finance")
    res2 = finance.run("check account balance for ACC-1001")

    # 3. Discover available agents
    print(agent.list_agents())  # ['finance', 'financial', 'support', 'treasury', ...]
"""
from __future__ import annotations

from typing import Any, Callable, Optional

from agent.base import AgentResult, BaseAgent
from agent.registry import get_agent, list_agents, register_agent


def run(
    prompt: str,
    *,
    agent_name: str = "support",
    interactive: bool = True,
    approval_callback: Optional[Callable] = None,
    auto_approve: bool = False,
    **kwargs: Any,
) -> AgentResult:
    """Run an agent against a natural language prompt.

    Args:
        prompt: Natural language user instruction.
        agent_name: Name of the agent to execute (default: 'support').
        interactive: Whether to prompt for human approval on the console for HITL actions.
        approval_callback: Optional callable `(tool, args, reason, approval_id) -> bool`.
        auto_approve: If True, automatically signs off on HITL escalations.
        **kwargs: Additional parameters passed to the agent constructor.

    Returns:
        AgentResult object with .text, .status, .tool_calls, and .run_id.
    """
    instance = get_agent(agent_name, **kwargs)
    return instance.run(
        prompt,
        interactive=interactive,
        approval_callback=approval_callback,
        auto_approve=auto_approve,
    )


__all__ = [
    "run",
    "get_agent",
    "list_agents",
    "register_agent",
    "BaseAgent",
    "AgentResult",
]

__version__ = "1.0.0"
