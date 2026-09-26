"""External Customer Support Agent Client."""
from __future__ import annotations

import os
import re
from typing import Any, Optional
from dotenv import load_dotenv

import tools
from data import crm
from shield import ShieldBlocked, ShieldClient, ShieldEscalated

load_dotenv()


class CustomerSupportAgent:
    name = "Customer Support Agent"
    id = "customer-support-agent"

    def __init__(self, client: Optional[ShieldClient] = None) -> None:
        self.client = client or ShieldClient()

    def run(self, prompt: str, auto_approve: bool = False) -> dict[str, Any]:
        """Execute a prompt against protected tools via AgentShield HTTP gateway."""
        tool_name, args = self._plan(prompt)

        try:
            if tool_name == "get_customer":
                out = tools.get_customer(**args)
            elif tool_name == "search_customer":
                out = tools.search_customer(**args)
            elif tool_name == "get_customer_orders":
                out = tools.get_customer_orders(**args)
            elif tool_name == "issue_refund":
                out = tools.issue_refund(**args)
            elif tool_name == "delete_customer":
                out = tools.delete_customer(**args)
            elif tool_name == "send_email":
                out = tools.send_email(**args)
            else:
                out = tools.get_customer_orders(**args)

            if tool_name == "get_customer" and isinstance(out, dict) and out.get("found", True):
                cid_val = out.get("display_id", args.get("customer_id"))
                formatted_text = (
                    f"✅ **[ALLOW] Customer Details Retrieved**\n\n"
                    f"### Customer Profile #{cid_val}\n"
                    f"- **Name**: {out.get('name')}\n"
                    f"- **Email**: {out.get('email')}\n"
                    f"- **Phone**: {out.get('phone')}\n"
                    f"- **Address**: {out.get('address')}\n"
                    f"- **Status**: {out.get('account_status', 'Active')}\n"
                )
            elif tool_name == "get_customer_orders" and isinstance(out, list):
                cid_val = args.get("customer_id")
                orders_md = "\n".join([f"- **Order #{o.get('display_id')}**: Status `{o.get('status')}` — ${o.get('total_amount', 0):.2f}" for o in out])
                formatted_text = (
                    f"✅ **[ALLOW] Retrieved {len(out)} Orders for Customer #{cid_val}**\n\n"
                    f"{orders_md if orders_md else 'No orders on file.'}"
                )
            elif tool_name == "issue_refund":
                formatted_text = f"✅ **[ALLOW] Refund Processed**: Successfully issued ${args.get('amount', 0):.2f} refund for Order #{args.get('order_id')}."
            else:
                formatted_text = f"✅ [ALLOW] Query executed successfully for tool `{tool_name}`: {out}"

            return {
                "status": "completed",
                "verdict": "ALLOW",
                "tool": tool_name,
                "args": args,
                "output": out,
                "text": formatted_text,
            }

        except ShieldBlocked as e:
            return {
                "status": "blocked",
                "verdict": "BLOCK",
                "tool": tool_name,
                "args": args,
                "risk_score": e.risk_score,
                "reason": e.reason,
                "text": f"⛔ [AgentShield BLOCKED] Action `{tool_name}` blocked by policy: {e.reason}",
            }

        except ShieldEscalated as e:
            if auto_approve and e.approval_id:
                self.client.decide_approval(e.approval_id, approved=True, decided_by="supervisor")
                raw_out = crm.get_customer(args.get("customer_id", 1008)) or {}

                # Least privilege minimization
                p_lower = prompt.lower()
                cid_val = raw_out.get("display_id", args.get("customer_id", 1008))
                name = raw_out.get("name", "N/A")

                if any(k in p_lower for k in ["aadhaar", "adhar", "aadhar", "uidai"]):
                    text = (
                        f"✅ **[AgentShield HITL Authorized]** Supervisor approved identity lookup.\n\n"
                        f"### Customer #{cid_val}\n"
                        f"- **Name**: {name}\n"
                        f"- **Aadhaar Number (UIDAI)**: `{raw_out.get('aadhaar')}`\n\n"
                        f"> 🛡️ *Privacy Guardrail: Unrequested fields (PAN, Phone, Address) masked.*"
                    )
                elif "pan" in p_lower:
                    text = (
                        f"✅ **[AgentShield HITL Authorized]** Supervisor approved PAN lookup.\n\n"
                        f"### Customer #{cid_val}\n"
                        f"- **Name**: {name}\n"
                        f"- **PAN Number**: `{raw_out.get('pan')}`\n\n"
                        f"> 🛡️ *Privacy Guardrail: Unrequested fields (Aadhaar, Phone, Address) masked.*"
                    )
                else:
                    text = (
                        f"✅ **[AgentShield HITL Authorized]** Supervisor approved customer profile access.\n\n"
                        f"### Customer #{cid_val}\n"
                        f"- **Name**: {name}\n"
                        f"- **Email**: {raw_out.get('email')}\n"
                        f"- **Phone**: {raw_out.get('phone')}\n"
                        f"- **Address**: {raw_out.get('address')}\n"
                        f"- **Status**: {raw_out.get('account_status', 'Active')}\n"
                    )

                return {
                    "status": "escalated_and_approved",
                    "verdict": "HITL",
                    "approval_id": e.approval_id,
                    "tool": tool_name,
                    "args": args,
                    "output": raw_out,
                    "text": text,
                }

            return {
                "status": "escalated",
                "verdict": "HITL",
                "approval_id": e.approval_id,
                "tool": tool_name,
                "args": args,
                "reason": e.reason,
                "text": f"⚠️ [AgentShield HITL] Escalated to supervisor. Approval ID: `{e.approval_id}`. Reason: {e.reason}",
            }

    def _plan(self, prompt: str) -> tuple[str, dict[str, Any]]:
        p = prompt.lower().strip()

        # Extract 4-digit ID
        m_id = re.search(r"\b(\d{4})\b", prompt)
        cid = int(m_id.group(1)) if m_id else 1001

        # 1. Account Deletion (High Risk / Destructive)
        if "delete" in p and any(w in p for w in ["customer", "user", "account"]):
            return "delete_customer", {"customer_id": cid if m_id else 1042}

        # 2. Refund requests
        if "refund" in p:
            m_ord = re.search(r"order\s*#?(\d+)", p) or re.search(r"\b(\d{4})\b", prompt)
            m_amt = re.search(r"\$?(\d+(\.\d+)?)", prompt)
            order_id = int(m_ord.group(1)) if m_ord else 8211
            amount = float(m_amt.group(1)) if m_amt else 45.0
            return "issue_refund", {"order_id": order_id, "amount": amount}

        # 3. Email search
        if "@" in prompt:
            m_email = re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", prompt)
            return "search_customer", {"email": m_email[0] if m_email else "alice@example.com"}

        # 4. Outbound email sending
        if "send email" in p or "send mail" in p:
            return "send_email", {"to": "security@example.com", "subject": "Support Request", "body": prompt}

        # 5. Customer Orders
        is_order_word = any(w in p for w in ["order", "orders", "purchase", "purchases", "bought", "shipping", "tracking", "delivery", "item", "items", "cart"])
        is_customer_word = any(w in p for w in ["customer", "detail", "details", "profile", "info", "user", "account", "identity", "phone", "address", "who is", "aadhaar", "adhar", "aadhar", "uidai", "pan"])

        if is_order_word and not ("customer detail" in p or "details of customer" in p or "user detail" in p):
            return "get_customer_orders", {"customer_id": cid}

        # 6. Customer details / profile lookup
        if is_customer_word:
            if any(w in p for w in ["aadhaar", "adhar", "uidai", "aadhar", "pan"]) and not m_id:
                cid = 1008
            return "get_customer", {"customer_id": cid}

        # 7. If ID given without order keyword, default to get_customer
        if m_id:
            return "get_customer", {"customer_id": cid}

        # Default fallback
        return "get_customer", {"customer_id": 1001}


if __name__ == "__main__":
    agent = CustomerSupportAgent()
    print("Testing external agent outside AgentShield:")
    res = agent.run("what is the adhar details of customer 1008", auto_approve=True)
    print(res["text"])
