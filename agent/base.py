"""BaseAgent interface and result abstractions for AgentShield clients."""
from __future__ import annotations

import abc
import asyncio
import logging
import sys
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from shield import ShieldClient

logger = logging.getLogger("agent.base")


@dataclass
class ToolExecutionRecord:
    tool: str
    arguments: dict[str, Any]
    verdict: str  # ALLOW | BLOCK | ESCALATE
    risk_score: float = 0.0
    reasons: list[str] = field(default_factory=list)
    decision_id: Optional[str] = None
    approval_id: Optional[str] = None
    output: Optional[Any] = None
    error: Optional[str] = None


@dataclass
class AgentResult:
    prompt: str
    agent_name: str
    status: str  # "completed" | "escalated_and_approved" | "escalated_and_denied" | "blocked" | "error"
    text: str
    tool_calls: list[ToolExecutionRecord] = field(default_factory=list)
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __str__(self) -> str:
        return self.text


ApprovalCallback = Callable[[str, dict[str, Any], str, Optional[str]], bool]


class BaseAgent(abc.ABC):
    """Abstract base class for all pluggable external agents."""

    name: str = "base"
    description: str = "Base Agent"

    def __init__(self, *, client: Optional[ShieldClient] = None) -> None:
        self.client = client or ShieldClient()

    @abc.abstractmethod
    async def run_async(
        self,
        prompt: str,
        *,
        run_id: Optional[str] = None,
        event_callback: Optional[Callable[[dict[str, Any]], Any]] = None,
        interactive: bool = True,
        approval_callback: Optional[ApprovalCallback] = None,
        auto_approve: bool = False,
    ) -> AgentResult:
        """Asynchronously execute the agent against a natural language prompt."""
        raise NotImplementedError

    def run(
        self,
        prompt: str,
        *,
        run_id: Optional[str] = None,
        event_callback: Optional[Callable[[dict[str, Any]], Any]] = None,
        interactive: bool = True,
        approval_callback: Optional[ApprovalCallback] = None,
        auto_approve: bool = False,
    ) -> AgentResult:
        """Synchronously execute the agent against a natural language prompt."""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            # If already inside an active event loop (e.g. Jupyter or nested loop)
            import nest_asyncio  # type: ignore
            nest_asyncio.apply()
            return loop.run_until_complete(
                self.run_async(
                    prompt,
                    run_id=run_id,
                    event_callback=event_callback,
                    interactive=interactive,
                    approval_callback=approval_callback,
                    auto_approve=auto_approve,
                )
            )

        return loop.run_until_complete(
            self.run_async(
                prompt,
                run_id=run_id,
                event_callback=event_callback,
                interactive=interactive,
                approval_callback=approval_callback,
                auto_approve=auto_approve,
            )
        )

    def handle_escalation(
        self,
        *,
        tool: str,
        arguments: dict[str, Any],
        reason: str,
        decision_id: Optional[str] = None,
        approval_id: Optional[str] = None,
        interactive: bool = True,
        approval_callback: Optional[ApprovalCallback] = None,
        auto_approve: bool = False,
    ) -> tuple[bool, str]:
        """Resolve a HITL escalation either automatically, via callback, or interactively via console."""
        # 1. Automatic approval mode
        if auto_approve:
            if approval_id:
                try:
                    self.client.decide_approval(
                        approval_id=approval_id,
                        approved=True,
                        decided_by="auto-approver",
                        note="Auto-approved by test runner configuration",
                    )
                except Exception as e:
                    logger.warning("Failed to record approval decision on gateway: %s", e)
            return True, "Auto-approved by policy override"

        # 2. Programmatic approval callback
        if approval_callback is not None:
            approved = approval_callback(tool, arguments, reason, approval_id)
            if approval_id:
                try:
                    self.client.decide_approval(
                        approval_id=approval_id,
                        approved=approved,
                        decided_by="callback-supervisor",
                        note="Decided via programmatic callback",
                    )
                except Exception as e:
                    logger.warning("Failed to record approval decision on gateway: %s", e)
            return approved, "Approved by supervisor callback" if approved else "Denied by supervisor callback"

        # 3. Interactive console prompt
        if interactive and sys.stdin.isatty():
            print("\n" + "=" * 65)
            print("⚠️  [AgentShield Security Gateway] Human Approval Required (HITL)")
            print("=" * 65)
            print(f"  Tool:         {tool}")
            print(f"  Arguments:    {arguments}")
            print(f"  Reason:       {reason}")
            if approval_id:
                print(f"  Approval ID:  {approval_id}")
            print("-" * 65)
            try:
                choice = input("Authorize this privileged action? [y/N]: ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                choice = "n"

            approved = choice in ("y", "yes")
            if approval_id:
                try:
                    self.client.decide_approval(
                        approval_id=approval_id,
                        approved=approved,
                        decided_by="cli-user",
                        note="User decided via CLI prompt",
                    )
                except Exception as e:
                    logger.warning("Failed to record approval decision on gateway: %s", e)

            return approved, "Authorized by supervisor" if approved else "Denied by supervisor"

        # 4. Default: require explicit approval in non-interactive environments
        return False, "Approval pending: non-interactive mode with no callback provided"
