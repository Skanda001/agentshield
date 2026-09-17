"""The gateway endpoint: evaluate a tool call and return a verdict."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_agent, get_db
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
        ),
    )
    return result.response


@router.get("/decisions", response_model=list[DecisionOut])
async def list_decisions(
    limit: int = 50,
    agent=Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Decision)
        .where(Decision.agent_id == agent.id)
        .order_by(Decision.created_at.desc())
        .limit(max(1, min(limit, 200)))
    )
    return list(result.scalars().all())