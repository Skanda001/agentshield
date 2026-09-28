"""The gateway endpoint: evaluate a tool call and return a verdict."""
from datetime import datetime
from typing import Optional

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
        data_classification=payload.data_classification,
    )
    return result.response


@router.get("/decisions", response_model=list[DecisionOut])
async def list_decisions(
    limit: int = 50,
    before: Optional[str] = None,
    agent=Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """List decisions for the current agent, newest first.

    Args:
        limit: Maximum rows to return (1–200).
        before: ISO 8601 datetime cursor — only return decisions created before this timestamp.
                Enables cursor-based pagination: pass the created_at of the last row received
                to fetch the next page.
    """
    query = select(Decision).where(Decision.agent_id == agent.id)

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