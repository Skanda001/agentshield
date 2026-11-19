from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_agent, get_db
from app.core.rate_limit import rate_limit
from app.db.models.decision import Decision
from app.gateway.decision_pipeline import run as run_pipeline
from app.gateway.tool_adapter import ToolCall
from app.schemas.decision import DecideRequest, DecideResponse, DecisionOut

router = APIRouter(tags=["decisions"])


@router.post("/decide", response_model=DecideResponse)
async def decide(
    payload: DecideRequest,
    request: Request,
    agent=Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
    _rl: None = Depends(rate_limit("decide", max_calls=120, window_seconds=60)),
):
    """Make a security decision. Rate limited: 120 requests/minute per agent IP."""
    result = await run_pipeline(
        db,
        agent=agent,
        call=ToolCall(
            tool=payload.tool,
            arguments=payload.arguments,
            resource_type=payload.resource_type,
            approval_id=payload.approval_id,
        ),
        data_classification=payload.data_classification,
    )
    return result.response


class DecisionStats(BaseModel):
    total: int
    allow: int
    escalate: int
    block: int


@router.get("/decisions/stats", response_model=DecisionStats)
async def get_decision_stats(
    db: AsyncSession = Depends(get_db),
    agent=Depends(get_current_agent),
):
    """Return aggregate lifetime stats scoped to the caller's tenant."""
    tid = agent.tenant_id

    def _query(extra_filter=None):
        stmt = select(func.count(Decision.id)).where(Decision.tenant_id == tid)
        if extra_filter is not None:
            stmt = stmt.where(extra_filter)
        return stmt

    total = await db.scalar(_query()) or 0
    allowed = await db.scalar(_query(Decision.verdict == "ALLOW")) or 0
    escalated = await db.scalar(_query(Decision.verdict.in_(["HITL", "ESCALATE"]))) or 0
    blocked = await db.scalar(_query(Decision.verdict == "BLOCK")) or 0

    return DecisionStats(
        total=total,
        allow=allowed,
        escalate=escalated,
        block=blocked,
    )


@router.get("/decisions", response_model=list[DecisionOut])
async def list_decisions(
    limit: int = 50,
    before: Optional[str] = None,
    agent_id: Optional[UUID] = None,
    agent=Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """List decisions for the caller's tenant, newest first.

    If agent_id is provided it must belong to the same tenant — cross-tenant
    agent_id values are silently ignored.
    """
    query = select(Decision).where(Decision.tenant_id == agent.tenant_id)

    # Only honour agent_id filter when it matches the caller's own agent
    # (prevents enumerating another tenant's agent decisions)
    if agent_id and agent_id == agent.id:
        query = query.where(Decision.agent_id == agent_id)

    if before:
        try:
            before_dt = datetime.fromisoformat(before.replace("Z", "+00:00"))
            query = query.where(Decision.created_at < before_dt)
        except ValueError:
            pass  # ignore malformed cursor, return from beginning

    query = query.order_by(Decision.created_at.desc()).limit(max(1, min(limit, 200)))
    result = await db.execute(query)
    return list(result.scalars().all())