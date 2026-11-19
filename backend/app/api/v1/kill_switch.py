"""Kill switch HTTP endpoints."""
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

_ADMIN_SCOPES = {"admin", "superadmin"}


def _require_admin(agent: Agent) -> None:
    """Raise 403 if the agent does not have an admin scope."""
    agent_scopes = set(agent.scopes or [])
    if not agent_scopes.intersection(_ADMIN_SCOPES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin scope required to manage kill switches",
        )


@router.post(
    "/kill-switch/activate",
    response_model=KillSwitchOut,
    status_code=status.HTTP_201_CREATED,
)
async def activate(
    payload: KillSwitchActivate,
    db: AsyncSession = Depends(get_db),
    agent: Agent = Depends(get_current_agent),
):
    # Global scope requires admin role
    if payload.scope == "global":
        _require_admin(agent)

    # Non-global scopes: target_id must belong to the caller's tenant
    if payload.scope in ("agent", "tenant") and payload.target_id:
        await svc.verify_target_in_tenant(
            db,
            scope=payload.scope,
            target_id=payload.target_id,
            tenant_id=agent.tenant_id,
        )

    # activated_by always comes from the authenticated principal
    activated_by = agent.name or str(agent.id)

    try:
        return await svc.activate(
            db,
            scope=payload.scope,
            target_id=payload.target_id,
            reason=payload.reason,
            activated_by=activated_by,
            tenant_id=agent.tenant_id,
        )
    except svc.KillSwitchError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/kill-switch/{kill_switch_id}/deactivate", response_model=KillSwitchOut)
async def deactivate(
    kill_switch_id: UUID,
    payload: KillSwitchDeactivate,
    db: AsyncSession = Depends(get_db),
    agent: Agent = Depends(get_current_agent),
):
    ks = await svc.get_switch(db, kill_switch_id)
    if not ks:
        raise HTTPException(status_code=404, detail="Kill switch not found")

    # Global switches can only be deactivated by admins
    if ks.scope == "global":
        _require_admin(agent)
    else:
        # Non-global: must belong to caller's tenant
        if str(ks.tenant_id) != str(agent.tenant_id):
            raise HTTPException(status_code=404, detail="Kill switch not found")

    # deactivated_by always from the authenticated principal
    deactivated_by = agent.name or str(agent.id)

    try:
        return await svc.deactivate(
            db,
            kill_switch_id=kill_switch_id,
            deactivated_by=deactivated_by,
            note=payload.note,
        )
    except svc.KillSwitchError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/kill-switch", response_model=list[KillSwitchOut])
async def list_switches(
    active_only: bool = Query(default=False),
    scope: str | None = Query(default=None, pattern=r"^(agent|tool|tenant|global)$"),
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    agent: Agent = Depends(get_current_agent),
):
    """List kill switches visible to the caller (own tenant + global switches)."""
    return await svc.list_switches(
        db,
        active_only=active_only,
        scope=scope,
        limit=limit,
        tenant_id=agent.tenant_id,
    )


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
