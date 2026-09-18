"""Approval service: create, list, decide, expire."""
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import chain as audit_chain
from app.db.models.agent import Agent
from app.db.models.approval import Approval
from app.db.models.decision import Decision


DEFAULT_TIMEOUT_MINUTES = 30


class ApprovalServiceError(Exception):
    pass


async def create_for_decision(
    db: AsyncSession,
    *,
    decision: Decision,
    agent: Agent,
    timeout_minutes: int = DEFAULT_TIMEOUT_MINUTES,
) -> Approval:
    """Create a pending approval for an ESCALATE decision."""
    existing = await db.execute(
        select(Approval).where(Approval.decision_id == decision.id)
    )
    if existing.scalar_one_or_none():
        raise ApprovalServiceError("Approval already exists for this decision")

    expires_at = datetime.now(timezone.utc) + timedelta(minutes=timeout_minutes)

    approval = Approval(
        decision_id=decision.id,
        agent_id=agent.id,
        tenant_id=agent.tenant_id,
        status="pending",
        tool=decision.tool,
        resource_type=decision.resource_type,
        request_context={
            "arguments": decision.arguments,
            "risk_score": decision.risk_score,
            "reasons": decision.reasons,
        },
        expires_at=expires_at,
    )
    db.add(approval)
    await db.commit()
    await db.refresh(approval)
    return approval


async def get_approval(db: AsyncSession, approval_id: UUID) -> Optional[Approval]:
    result = await db.execute(select(Approval).where(Approval.id == approval_id))
    return result.scalar_one_or_none()


async def list_approvals(
    db: AsyncSession,
    *,
    tenant_id: Optional[UUID] = None,
    status: Optional[str] = None,
    limit: int = 50,
) -> list[Approval]:
    stmt = select(Approval).order_by(Approval.created_at.desc()).limit(max(1, min(limit, 500)))
    if tenant_id:
        stmt = stmt.where(Approval.tenant_id == tenant_id)
    if status:
        stmt = stmt.where(Approval.status == status)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def decide(
    db: AsyncSession,
    *,
    approval: Approval,
    approved: bool,
    decided_by: str,
    note: Optional[str] = None,
) -> Approval:
    """Record a human's decision and append to the audit chain."""
    if approval.status != "pending":
        raise ApprovalServiceError(f"Approval already decided (status={approval.status})")

    approval.status = "approved" if approved else "denied"
    approval.decided_by = decided_by
    approval.decision_note = note
    approval.decided_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(approval)

    await audit_chain.append_event(
        db,
        event_type="approval.decided",
        payload={
            "approval_id": str(approval.id),
            "decision_id": str(approval.decision_id),
            "approved": approved,
            "decided_by": decided_by,
            "note": note,
            "tool": approval.tool,
        },
        agent_id=approval.agent_id,
        tenant_id=approval.tenant_id,
    )

    return approval


async def expire_stale(db: AsyncSession) -> int:
    """Mark pending approvals past expires_at as expired. Returns count."""
    now = datetime.now(timezone.utc)
    stmt = select(Approval).where(
        Approval.status == "pending", Approval.expires_at <= now
    )
    result = await db.execute(stmt)
    stale = list(result.scalars().all())

    for approval in stale:
        approval.status = "expired"
        approval.decided_by = "system"
        approval.decision_note = "Auto-expired after timeout"
        approval.decided_at = now
        await db.commit()
        await db.refresh(approval)

        await audit_chain.append_event(
            db,
            event_type="approval.expired",
            payload={
                "approval_id": str(approval.id),
                "decision_id": str(approval.decision_id),
                "tool": approval.tool,
            },
            agent_id=approval.agent_id,
            tenant_id=approval.tenant_id,
        )

    return len(stale)