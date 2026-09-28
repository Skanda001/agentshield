"""
Real email support agent.

Flow per email:
  1. Groq LLM reads the email → decides which tool to call + arguments
  2. @protect sends a decide request to AgentShield
  3. ALLOW  → tool executes → Groq writes a professional reply
     BLOCK  → reply explains the security block
     HITL   → reply says supervisor will review
  4. Reply is sent back via Gmail SMTP
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

from groq import Groq

import tools
from shield import ShieldBlocked, ShieldEscalated
from email_client import InboundEmail

log = logging.getLogger("email_agent")

# ── Groq setup ────────────────────────────────────────────────────────────────

GROQ_MODEL = "llama-3.3-70b-versatile"

DECISION_SYSTEM_PROMPT = """You are the decision engine for an AI customer support agent.

Read the incoming support email and decide which ONE tool to call.

Available tools:
  get_customer(customer_id: int)              – customer profile by numeric ID
  search_customer(email: str)                 – find customer by email address
  get_customer_orders(customer_id: int)       – all orders for a customer
  issue_refund(order_id: int, amount: float)  – process a refund
  send_email(to: str, subject: str, body: str)– send an outbound email
  delete_customer(customer_id: int)           – delete a customer account

Rules:
- Extract customer IDs (4-digit numbers like 1001, 1008, 1042) from the email.
- Extract order IDs (4-digit numbers like 8211, 4821) from the email.
- Extract amounts ($45, 129.99) from the email.
- If no ID is mentioned, use customer_id 1001 as default.
- If the email contains an email address (other than the sender), use search_customer.
- If the email asks about orders/delivery/shipping, use get_customer_orders.
- If the email asks to send something to a third party, use send_email.

Respond ONLY with valid JSON:
{
  "tool": "tool_name",
  "args": { ...arguments as key-value pairs... },
  "reasoning": "one sentence explaining your choice"
}"""

REPLY_SYSTEM_PROMPT = """You are a professional, warm customer support agent.
Write a concise reply email to the customer based on the information provided.
- Be helpful and empathetic.
- Keep it under 150 words.
- Do NOT mention internal tool names, system names, or API details.
- Sign off as: AgentShield Support Team.
- Do NOT include a subject line."""


class EmailSupportAgent:
    def __init__(self) -> None:
        api_key = os.getenv("GROQ_API_KEY", "")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY environment variable is not set")
        self.groq = Groq(api_key=api_key)

    # ── Public API ────────────────────────────────────────────────────────────

    def process(self, inbound: InboundEmail) -> dict[str, Any]:
        """
        Process one inbound email end-to-end.
        Returns a dict with verdict, tool, reply text, etc.
        """
        log.info("📨 From: %s | Subject: %s", inbound.from_addr, inbound.subject)

        # Step 1 — LLM decides which tool to call
        tool_name, args, reasoning = self._decide(inbound)
        log.info("🤖 LLM → tool=%s args=%s", tool_name, args)
        log.info("   Reasoning: %s", reasoning)

        # Step 2 — Execute tool (hits @protect → AgentShield)
        try:
            result = self._execute(tool_name, args)
            reply  = self._compose_reply(inbound, tool_name, args, result)
            log.info("✅ ALLOW | tool=%s", tool_name)
            return {
                "verdict": "ALLOW",
                "tool": tool_name,
                "args": args,
                "result": result,
                "reply": reply,
            }

        except ShieldBlocked as e:
            reply = self._blocked_reply(inbound, e.reason)
            log.warning("⛔ BLOCK | tool=%s | %s", tool_name, e.reason)
            return {
                "verdict": "BLOCK",
                "tool": tool_name,
                "args": args,
                "reason": e.reason,
                "reply": reply,
            }

        except ShieldEscalated as e:
            reply = self._hitl_reply(inbound, e.reason, e.approval_id or "")
            log.warning("⚠️  HITL | tool=%s | approval=%s", tool_name, e.approval_id)
            return {
                "verdict": "HITL",
                "tool": tool_name,
                "args": args,
                "approval_id": e.approval_id,
                "reason": e.reason,
                "reply": reply,
            }

        except Exception as exc:
            log.error("❌ Tool error: %s", exc)
            return {
                "verdict": "ERROR",
                "tool": tool_name,
                "reply": (
                    "Dear Customer,\n\n"
                    "We encountered an error processing your request. "
                    "Our team has been notified and will follow up shortly.\n\n"
                    "Best regards,\nAgentShield Support Team"
                ),
            }

    # ── Private helpers ───────────────────────────────────────────────────────

    def _decide(self, inbound: InboundEmail) -> tuple[str, dict, str]:
        """Ask Groq which tool to call. Returns (tool_name, args, reasoning)."""
        user_msg = (
            f"From: {inbound.from_addr}\n"
            f"Subject: {inbound.subject}\n\n"
            f"{inbound.body}"
        )
        try:
            resp = self.groq.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": DECISION_SYSTEM_PROMPT},
                    {"role": "user",   "content": user_msg},
                ],
                temperature=0.1,
                max_tokens=300,
                response_format={"type": "json_object"},
            )
            data = json.loads(resp.choices[0].message.content)
            return (
                data.get("tool", "get_customer"),
                data.get("args", {"customer_id": 1001}),
                data.get("reasoning", ""),
            )
        except Exception as exc:
            log.warning("LLM decision fallback: %s", exc)
            return "get_customer", {"customer_id": 1001}, "LLM unavailable — using fallback"

    def _execute(self, tool_name: str, args: dict) -> Any:
        """Execute the named tool. @protect decorator handles AgentShield call."""
        tool_map = {
            "get_customer":        tools.get_customer,
            "search_customer":     tools.search_customer,
            "get_customer_orders": tools.get_customer_orders,
            "issue_refund":        tools.issue_refund,
            "send_email":          tools.send_email,
            "delete_customer":     tools.delete_customer,
        }
        fn = tool_map.get(tool_name)
        if not fn:
            raise ValueError(f"Unknown tool: {tool_name}")

        # Convert arg types (JSON gives strings, tools may need int/float)
        cleaned: dict = {}
        for k, v in args.items():
            if k in ("customer_id", "order_id") and not isinstance(v, int):
                try:
                    cleaned[k] = int(v)
                except (TypeError, ValueError):
                    cleaned[k] = v
            elif k == "amount" and not isinstance(v, float):
                try:
                    cleaned[k] = float(v)
                except (TypeError, ValueError):
                    cleaned[k] = v
            else:
                cleaned[k] = v

        return fn(**cleaned)

    def _compose_reply(
        self,
        inbound: InboundEmail,
        tool: str,
        args: dict,
        result: Any,
    ) -> str:
        """Ask Groq to write a professional reply based on the tool result."""
        prompt = (
            f"Original email:\n"
            f"From: {inbound.from_addr}\n"
            f"Subject: {inbound.subject}\n"
            f"Body: {inbound.body}\n\n"
            f"You ran the support tool and got this result:\n"
            f"{json.dumps(result, default=str, indent=2)}\n\n"
            f"Write the reply email body."
        )
        try:
            resp = self.groq.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": REPLY_SYSTEM_PROMPT},
                    {"role": "user",   "content": prompt},
                ],
                temperature=0.7,
                max_tokens=300,
            )
            return resp.choices[0].message.content.strip()
        except Exception:
            return (
                f"Dear Customer,\n\n"
                f"Your request has been processed.\n\n"
                f"Result: {result}\n\n"
                f"Best regards,\nAgentShield Support Team"
            )

    # ── Reply templates ───────────────────────────────────────────────────────

    @staticmethod
    def _blocked_reply(inbound: InboundEmail, reason: str) -> str:
        return (
            f"Dear Customer,\n\n"
            f"Thank you for reaching out. Unfortunately your request could not be completed.\n\n"
            f"🛡️ Security Notice: Our AI security gateway (AgentShield) flagged this request "
            f"as a potential policy violation and blocked it automatically.\n\n"
            f"Reason: {reason}\n\n"
            f"If you believe this is a mistake, please contact us directly.\n\n"
            f"Best regards,\n"
            f"AgentShield Support Team\n"
            f"Powered by AgentShield Security Gateway"
        )

    @staticmethod
    def _hitl_reply(inbound: InboundEmail, reason: str, approval_id: str) -> str:
        return (
            f"Dear Customer,\n\n"
            f"Thank you for your request. It requires supervisor approval before we can proceed.\n\n"
            f"⚠️ Status: Escalated for human review\n"
            f"Reference ID: {approval_id}\n"
            f"Reason: {reason}\n\n"
            f"A supervisor will review and respond within 30 minutes.\n\n"
            f"Best regards,\n"
            f"AgentShield Support Team\n"
            f"Powered by AgentShield Security Gateway"
        )
