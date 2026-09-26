"""Financial and Accounting Agent for testing multi-agent pluggability with AgentShield."""
from __future__ import annotations

import logging
import re
from typing import Any, Optional

from agent.base import AgentResult, ApprovalCallback, BaseAgent, ToolExecutionRecord
from agent.registry import register_agent
from shield import ShieldBlocked, ShieldClient, ShieldEscalated, protect

logger = logging.getLogger("agent.finance")


# In-memory account ledger
_ACCOUNTS = {
    "ACC-1001": {"owner": "Alice Sharma", "balance": 15420.50},
    "ACC-1008": {"owner": "Priya Verma", "balance": 8340.00},
    "ACC-9999": {"owner": "Corporate Treasury", "balance": 500000.00},
}


# ─────────────────────────────────────────────────────────────
# Protected Financial Tools
# ─────────────────────────────────────────────────────────────

@protect(tool="get_account_balance", resource_type="payment", data_classification="internal")
def get_balance_tool(account_id: str) -> dict[str, Any]:
    acc = _ACCOUNTS.get(account_id)
    if not acc:
        return {"found": False, "account_id": account_id}
    return {"found": True, "account_id": account_id, "owner": acc["owner"], "balance": acc["balance"]}


@protect(tool="transfer_funds", resource_type="payment", data_classification="restricted")
def transfer_funds_tool(from_account: str, to_account: str, amount: float) -> dict[str, Any]:
    src = _ACCOUNTS.get(from_account)
    if not src or src["balance"] < amount:
        return {"success": False, "error": "Insufficient funds or account not found"}
    src["balance"] -= amount
    if to_account in _ACCOUNTS:
        _ACCOUNTS[to_account]["balance"] += amount
    return {"success": True, "from": from_account, "to": to_account, "amount": amount, "new_balance": src["balance"]}


@protect(tool="wire_funds_offshore", resource_type="payment", data_classification="restricted")
def wire_funds_offshore_tool(to_iban: str, amount: float) -> dict[str, Any]:
    return {"status": "unauthorized"}


# ─────────────────────────────────────────────────────────────
# Financial Agent Implementation
# ─────────────────────────────────────────────────────────────

@register_agent("finance", "financial", "treasury")
class FinancialAgent(BaseAgent):
    """External AI Financial Agent managing accounts, balances, and fund transfers."""

    name = "finance"
    description = "Enterprise Financial Agent managing accounting ledgers, treasury balances, and wire transfers."

    async def run_async(
        self,
        prompt: str,
        *,
        run_id: Optional[str] = None,
        event_callback: Optional[Any] = None,
        interactive: bool = True,
        approval_callback: Optional[ApprovalCallback] = None,
        auto_approve: bool = False,
        **kwargs: Any,
    ) -> AgentResult:
        tool_name, tool_args = self._determine_tool_call(prompt)
        record = ToolExecutionRecord(tool=tool_name, arguments=tool_args, verdict="UNKNOWN")

        try:
            if tool_name == "get_account_balance":
                output = get_balance_tool(**tool_args)
            elif tool_name == "transfer_funds":
                output = transfer_funds_tool(**tool_args)
            elif tool_name == "wire_funds_offshore":
                output = wire_funds_offshore_tool(**tool_args)
            else:
                raise ValueError(f"Unknown tool: {tool_name}")

            record.verdict = "ALLOW"
            record.output = output
            text = f"✅ **Financial Query Successful**: {output}"
            return AgentResult(prompt=prompt, agent_name=self.name, status="completed", text=text, tool_calls=[record])

        except ShieldBlocked as e:
            record.verdict = "BLOCK"
            record.risk_score = e.risk_score
            record.reasons = [e.reason]
            text = f"⛔ **[AgentShield BLOCKED] Unauthorized Financial Operation**: {e.reason}"
            return AgentResult(prompt=prompt, agent_name=self.name, status="blocked", text=text, tool_calls=[record])

        except ShieldEscalated as e:
            record.verdict = "ESCALATE"
            record.decision_id = e.decision_id
            record.approval_id = e.approval_id
            record.risk_score = e.risk_score
            record.reasons = [e.reason]

            approved, note = self.handle_escalation(
                tool=tool_name,
                arguments=tool_args,
                reason=e.reason,
                decision_id=e.decision_id,
                approval_id=e.approval_id,
                interactive=interactive,
                approval_callback=approval_callback,
                auto_approve=auto_approve,
            )

            if approved:
                # Execute direct transfer
                raw_out = transfer_funds_tool.__wrapped__(**tool_args) if hasattr(transfer_funds_tool, "__wrapped__") else {}
                text = f"✅ **[AgentShield HITL Authorized]** Fund transfer of ${tool_args.get('amount')} authorized by supervisor."
                return AgentResult(prompt=prompt, agent_name=self.name, status="escalated_and_approved", text=text, tool_calls=[record])
            else:
                text = f"⛔ **[AgentShield HITL Denied]** Fund transfer was denied by supervisor ({note})."
                return AgentResult(prompt=prompt, agent_name=self.name, status="escalated_and_denied", text=text, tool_calls=[record])

    def _determine_tool_call(self, prompt: str) -> tuple[str, dict[str, Any]]:
        p = prompt.lower()
        if "wire" in p or "offshore" in p:
            return "wire_funds_offshore", {"to_iban": "CH93-0000-0000", "amount": 50000.0}

        if "transfer" in p or "send" in p:
            amt_match = re.search(r"\$?\s*(\d+(?:\.\d{1,2})?)", prompt)
            amt = float(amt_match.group(1)) if amt_match else 500.0
            return "transfer_funds", {"from_account": "ACC-1001", "to_account": "ACC-1008", "amount": amt}

        return "get_account_balance", {"account_id": "ACC-1001"}
