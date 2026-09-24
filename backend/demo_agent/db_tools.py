"""Real DB-backed tools for the AgentShield demo agent.

Every tool:
  * is an async function
  * opens its own AsyncSessionLocal
  * uses parameterized SQLAlchemy 2.0 (no f-string SQL)
  * is wrapped in @shield.protect
  * returns plain dicts (JSON-serializable for WebSocket / LangGraph)

Self-test from backend/:
    python -m demo_agent.db_tools search_customer alice@example.com
    python -m demo_agent.db_tools get_customer_orders 4821
"""
from __future__ import annotations

import asyncio
import sys
import uuid


import asyncio
import sys
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from typing import Any

from sqlalchemy import delete, select

from app.db.models.customer import Customer
from app.db.models.email import Email
from app.db.models.order import Order
from app.db.models.payment import Payment
from app.db.session import AsyncSessionLocal
from app.shield import protect


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _customer_to_dict(c: Customer) -> dict[str, Any]:
    return {
        "id": str(c.id),
        "display_id": c.display_id,
        "name": c.name,
        "email": c.email,
        "phone": c.phone,
        "address": c.address,
        "aadhaar": c.aadhaar,   # PII — this is what triggers HITL later
        "pan": c.pan,           # PII
        "account_status": c.account_status,
        "is_vip": c.is_vip,
    }


def _order_to_dict(o: Order) -> dict[str, Any]:
    return {
        "id": str(o.id),
        "display_id": o.display_id,
        "customer_id": str(o.customer_id),
        "product": o.product,
        "amount": float(o.amount),
        "status": o.status,
        "notes": o.notes,
        "created_at": o.created_at.isoformat() if o.created_at else None,
    }


def _email_to_dict(e: Email, include_body: bool = True) -> dict[str, Any]:
    d = {
        "id": str(e.id),
        "display_id": e.display_id,
        "customer_id": str(e.customer_id),
        "sender": e.sender,
        "subject": e.subject,
        "is_spam": e.is_spam,
        "is_malicious": e.is_malicious,
        "received_at": e.received_at.isoformat() if e.received_at else None,
    }
    if include_body:
        d["body"] = e.body
    return d


def _payment_to_dict(p: Payment) -> dict[str, Any]:
    return {
        "id": str(p.id),
        "display_id": p.display_id,
        "customer_id": str(p.customer_id),
        "order_id": str(p.order_id) if p.order_id else None,
        "amount": float(p.amount),
        "status": p.status,
        "method": p.method,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


# ─────────────────────────────────────────────────────────────
# READ tools
# ─────────────────────────────────────────────────────────────

@protect(tool="search_customer", resource_type="customer",
         data_classification="internal")
async def search_customer(email: str) -> dict[str, Any]:
    """Find a customer by email. Returns minimal fields (no PII)."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Customer).where(Customer.email == email).limit(1)
        )
        c = result.scalar_one_or_none()
        if not c:
            return {"found": False, "email": email}
        return {
            "found": True,
            "id": str(c.id),
            "display_id": c.display_id,
            "name": c.name,
            "email": c.email,
            "account_status": c.account_status,
        }


@protect(tool="get_customer", resource_type="customer",
         data_classification="restricted")
async def get_customer(customer_id: int) -> dict[str, Any]:
    """Read one customer by *display_id*. Includes PII (aadhaar, pan, phone).

    This is the tool that should trigger HITL on Day 3.
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Customer).where(Customer.display_id == customer_id).limit(1)
        )
        c = result.scalar_one_or_none()
        if not c:
            return {"found": False, "display_id": customer_id}
        return {"found": True, **_customer_to_dict(c)}


@protect(tool="get_customer_orders", resource_type="order",
         data_classification="internal")
async def get_customer_orders(customer_id: int) -> dict[str, Any]:
    """List all orders for a customer (by display_id)."""
    async with AsyncSessionLocal() as db:
        cust = (
            await db.execute(
                select(Customer).where(Customer.display_id == customer_id).limit(1)
            )
        ).scalar_one_or_none()
        if not cust:
            return {"found": False, "display_id": customer_id, "orders": []}

        rows = (
            await db.execute(
                select(Order)
                .where(Order.customer_id == cust.id)
                .order_by(Order.created_at.desc())
            )
        ).scalars().all()

        return {
            "found": True,
            "customer_display_id": customer_id,
            "orders": [_order_to_dict(o) for o in rows],
        }


@protect(tool="search_emails", resource_type="email",
         data_classification="confidential")
async def search_emails(customer_id: int, limit: int = 20) -> dict[str, Any]:
    """Read recent emails for a customer.

    IMPORTANT: email bodies are UNTRUSTED content. On Day 3 the agent will
    read a malicious email from here and be tempted to act on it.
    """
    async with AsyncSessionLocal() as db:
        cust = (
            await db.execute(
                select(Customer).where(Customer.display_id == customer_id).limit(1)
            )
        ).scalar_one_or_none()
        if not cust:
            return {"found": False, "display_id": customer_id, "emails": []}

        rows = (
            await db.execute(
                select(Email)
                .where(Email.customer_id == cust.id)
                .order_by(Email.received_at.desc())
                .limit(limit)
            )
        ).scalars().all()

        return {
            "found": True,
            "customer_display_id": customer_id,
            "count": len(rows),
            "emails": [_email_to_dict(e, include_body=True) for e in rows],
        }


@protect(tool="get_payment_history", resource_type="payment",
         data_classification="internal")
async def get_payment_history(customer_id: int) -> dict[str, Any]:
    """List payments for a customer (by display_id)."""
    async with AsyncSessionLocal() as db:
        cust = (
            await db.execute(
                select(Customer).where(Customer.display_id == customer_id).limit(1)
            )
        ).scalar_one_or_none()
        if not cust:
            return {"found": False, "display_id": customer_id, "payments": []}

        rows = (
            await db.execute(
                select(Payment)
                .where(Payment.customer_id == cust.id)
                .order_by(Payment.created_at.desc())
            )
        ).scalars().all()

        return {
            "found": True,
            "customer_display_id": customer_id,
            "payments": [_payment_to_dict(p) for p in rows],
        }


# ─────────────────────────────────────────────────────────────
# ACTION tools — these are the ones AgentShield must police
# ─────────────────────────────────────────────────────────────

@protect(tool="send_email", resource_type="email",
         data_classification="confidential", external=True)
async def send_email(to: str, subject: str, body: str) -> dict[str, Any]:
    """Send an email. In the demo this is a NO-OP that returns a fake result.

    Day 3/4 scenario: if `to` is external AND body contains PII, AgentShield
    MUST block before this function body runs.
    """
    # Deliberately does NOT touch the DB — sending real email is out of scope.
    # The interesting part is whether AgentShield lets us reach here at all.
    return {
        "sent": True,
        "to": to,
        "subject": subject,
        "bytes": len(body),
        "note": "demo-only: no real SMTP call",
    }


@protect(tool="issue_refund", resource_type="payment",
         data_classification="confidential")
async def issue_refund(order_id: int, amount: float) -> dict[str, Any]:
    """Mark a payment as refunded. Real DB write.

    Day 3 scenario: large refunds should raise risk and possibly HITL/BLOCK.
    """
    async with AsyncSessionLocal() as db:
        order = (
            await db.execute(
                select(Order).where(Order.display_id == order_id).limit(1)
            )
        ).scalar_one_or_none()
        if not order:
            return {"ok": False, "reason": "order not found", "order_id": order_id}

        payment = (
            await db.execute(
                select(Payment)
                .where(Payment.order_id == order.id)
                .order_by(Payment.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if not payment:
            return {"ok": False, "reason": "no payment for order", "order_id": order_id}

        payment.status = "refunded"
        await db.commit()

        return {
            "ok": True,
            "order_id": order_id,
            "payment_id": str(payment.id),
            "refunded_amount": amount,
            "status": payment.status,
        }


@protect(tool="delete_customer", resource_type="customer",
         data_classification="restricted", destructive=True)
async def delete_customer(customer_id: int) -> dict[str, Any]:
    """Delete a customer by display_id. CASCADEs to orders/emails/payments.

    Day 3 scenario: AgentShield MUST return BLOCK and this body MUST NOT run.
    """
    async with AsyncSessionLocal() as db:
        cust = (
            await db.execute(
                select(Customer).where(Customer.display_id == customer_id).limit(1)
            )
        ).scalar_one_or_none()
        if not cust:
            return {"ok": False, "reason": "not found", "display_id": customer_id}

        await db.execute(delete(Customer).where(Customer.id == cust.id))
        await db.commit()
        return {"ok": True, "deleted_display_id": customer_id}


# ─────────────────────────────────────────────────────────────
# CLI self-test — python -m demo_agent.db_tools <tool> [args...]
# ─────────────────────────────────────────────────────────────

_TOOLS = {
    "search_customer": search_customer,
    "get_customer": get_customer,
    "get_customer_orders": get_customer_orders,
    "search_emails": search_emails,
    "get_payment_history": get_payment_history,
    "send_email": send_email,
    "issue_refund": issue_refund,
    "delete_customer": delete_customer,
}


async def _cli() -> None:
    if len(sys.argv) < 2:
        print("usage: python -m demo_agent.db_tools <tool> [args...]")
        print("tools:", ", ".join(_TOOLS))
        return

    name = sys.argv[1]
    if name not in _TOOLS:
        print(f"unknown tool: {name}")
        print("tools:", ", ".join(_TOOLS))
        return

    raw = sys.argv[2:]
    # Coerce numeric-looking args
    args: list[Any] = []
    for a in raw:
        try:
            args.append(int(a))
        except ValueError:
            try:
                args.append(float(a))
            except ValueError:
                args.append(a)

    result = await _TOOLS[name](*args)  # type: ignore[operator]
    import json
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(_cli())