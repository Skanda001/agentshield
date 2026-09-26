"""External Financial Agent Client."""
from __future__ import annotations

import re
from typing import Any, Optional
from dotenv import load_dotenv

from shield import ShieldBlocked, ShieldClient, ShieldEscalated, protect

load_dotenv()

_ACCOUNTS = {
    "ACC-1001": {"owner": "Alice Sharma", "balance": 15420.50},
    "ACC-1008": {"owner": "Priya Verma", "balance": 8340.00},
}


@protect(tool="get_account_balance", resource_type="payment", data_classification="internal")
def get_account_balance(account_id: str) -> dict[str, Any]:
    acc = _ACCOUNTS.get(account_id)
    return acc or {"found": False, "account_id": account_id}


@protect(tool="transfer_funds", resource_type="payment", data_classification="restricted")
def transfer_funds(from_account: str, to_account: str, amount: float) -> dict[str, Any]:
    src = _ACCOUNTS.get(from_account)
    if not src or src["balance"] < amount:
        return {"success": False, "error": "Insufficient funds"}
    src["balance"] -= amount
    return {"success": True, "from": from_account, "to": to_account, "amount": amount, "new_balance": src["balance"]}


@protect(tool="wire_funds_offshore", resource_type="payment", data_classification="restricted")
def wire_funds_offshore(target_account: str, amount: float) -> dict[str, Any]:
    return {"success": False, "error": "Offshore wire blocked by policy"}


class FinancialAgent:
    name = "Financial & Treasury Agent"
    id = "financial-agent"

    def __init__(self, client: Optional[ShieldClient] = None) -> None:
        self.client = client or ShieldClient()

    def run(self, prompt: str, auto_approve: bool = False) -> dict[str, Any]:
        p = prompt.lower()
        if "wire" in p or "offshore" in p:
            tool_name = "wire_funds_offshore"
            args = {"target_account": "ACC-9999", "amount": 1000000.0}
        elif any(w in p for w in ["transfer", "send", "move", "pay"]):
            tool_name = "transfer_funds"
            args = {"from_account": "ACC-1001", "to_account": "ACC-1008", "amount": 500.0}
        else:
            tool_name = "get_account_balance"
            args = {"account_id": "ACC-1001"}

        try:
            if tool_name == "wire_funds_offshore":
                out = wire_funds_offshore(**args)
            elif tool_name == "transfer_funds":
                out = transfer_funds(**args)
            else:
                out = get_account_balance(**args)
            return {"status": "completed", "verdict": "ALLOW", "tool": tool_name, "args": args, "output": out, "text": f"✅ [ALLOW] Financial transaction executed: {out}"}
        except ShieldBlocked as e:
            return {"status": "blocked", "verdict": "BLOCK", "tool": tool_name, "args": args, "reason": e.reason, "text": f"⛔ [AgentShield BLOCKED] Financial action refused: {e.reason}"}
        except ShieldEscalated as e:
            if auto_approve and e.approval_id:
                self.client.decide_approval(e.approval_id, approved=True, decided_by="supervisor")
                return {"status": "escalated_and_approved", "verdict": "HITL", "tool": tool_name, "args": args, "text": f"✅ **[AgentShield HITL Authorized]** Fund transfer of ${args['amount']} authorized by supervisor."}
            return {"status": "escalated", "verdict": "HITL", "tool": tool_name, "args": args, "approval_id": e.approval_id, "text": f"⚠️ [AgentShield HITL] Transfer requires supervisor sign-off (Approval ID: {e.approval_id})."}

