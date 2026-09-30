from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_agent, get_optional_agent, get_db
from app.db.models.decision import Decision
from app.gateway.decision_pipeline import run as run_pipeline
from app.gateway.tool_adapter import ToolCall
from app.schemas.decision import DecideRequest, DecideResponse, DecisionOut

router = APIRouter(tags=["decisions"])


@router.post("/decide", response_model=DecideResponse)
async def decide(
    payload: DecideRequest,
    agent=Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
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
    agent_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    _agent=Depends(get_optional_agent),
):
    """Return aggregate lifetime stats across all decisions (or by agent)."""
    def _query(extra_filter=None):
        stmt = select(func.count(Decision.id))
        if agent_id:
            stmt = stmt.where(Decision.agent_id == agent_id)
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
    _agent=Depends(get_optional_agent),
    db: AsyncSession = Depends(get_db),
):
    """List decisions for dashboard monitoring, newest first.

    If agent_id is provided, filter to that agent.
    If not provided, returns all gateway decisions matching the audit log.
    """
    query = select(Decision)
    if agent_id:
        query = query.where(Decision.agent_id == agent_id)

    # Fix #23: cursor-based pagination
    if before:
        try:
            before_dt = datetime.fromisoformat(before.replace("Z", "+00:00"))
            query = query.where(Decision.created_at < before_dt)
        except ValueError:
            pass  # ignore malformed cursor, return from beginning

    query = query.order_by(Decision.created_at.desc()).limit(max(1, min(limit, 200)))
    result = await db.execute(query)
    return list(result.scalars().all())