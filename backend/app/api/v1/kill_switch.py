"""Kill switch HTTP endpoints."""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_agent, get_db
from app.db.models.agent import Agent
from app.kill_switch.controller import check as check_kill_switch
from app.schemas.kill_switch import (
    KillSwitchActivate,
    KillSwitchCheck,
    KillSwitchDeactivate,
    KillSwitchOut,
)
from app.services import kill_switch_service as svc

router = APIRouter(tags=["kill-switch"])


@router.post(
    "/kill-switch/activate",
    response_model=KillSwitchOut,
    status_code=status.HTTP_201_CREATED,
)
async def activate(
    payload: KillSwitchActivate,
    db: AsyncSession = Depends(get_db),
    _agent=Depends(get_current_agent),
):
    try:
        return await svc.activate(
            db,
            scope=payload.scope,
            target_id=payload.target_id,
            reason=payload.reason,
            activated_by=payload.activated_by,
        )
    except svc.KillSwitchError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/kill-switch/{kill_switch_id}/deactivate", response_model=KillSwitchOut)
async def deactivate(
    kill_switch_id: UUID,
    payload: KillSwitchDeactivate,
    db: AsyncSession = Depends(get_db),
    _agent=Depends(get_current_agent),
):
    try:
        return await svc.deactivate(
            db,
            kill_switch_id=kill_switch_id,
            deactivated_by=payload.deactivated_by,
            note=payload.note,
        )
    except svc.KillSwitchError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/kill-switch", response_model=list[KillSwitchOut])
async def list_switches(
    active_only: bool = Query(default=False),
    scope: Optional[str] = Query(default=None, pattern=r"^(agent|tool|tenant|global)$"),
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _agent=Depends(get_current_agent),
):
    return await svc.list_switches(db, active_only=active_only, scope=scope, limit=limit)


@router.get("/kill-switch/status", response_model=KillSwitchCheck)
async def status_check(
    tool: str = Query(min_length=1, max_length=120),
    db: AsyncSession = Depends(get_db),
    agent: Agent = Depends(get_current_agent),
):
    """Check if the calling agent is currently blocked by any kill switch."""
    result = await check_kill_switch(
        db,
        agent_id=agent.id,
        tenant_id=agent.tenant_id,
        tool=tool,
    )
    return KillSwitchCheck(
        blocked=result.blocked,
        reason=result.reason,
        scope=result.scope,
        kill_switch_id=result.kill_switch_id,
    )