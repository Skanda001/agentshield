"""HTTP endpoints for tenants and agents."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_current_agent, get_db
from app.core.security import create_agent_token
from app.schemas.agent import (
    AgentCreate,
    AgentCreateResponse,
    AgentOut,
    AgentTokenRequest,
    AgentTokenResponse,
    TenantCreate,
    TenantOut,
)
from app.services import agent_registry as registry

router = APIRouter(tags=["agents"])


# ─── Tenants ────────────────────────────────────────────────────

@router.post(
    "/tenants",
    response_model=TenantOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_tenant(
    payload: TenantCreate,
    db: AsyncSession = Depends(get_db),
):
    try:
        tenant = await registry.create_tenant(
            db, name=payload.name, slug=payload.slug
        )
    except registry.RegistryError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return tenant


# ─── Agents ─────────────────────────────────────────────────────

@router.post(
    "/agents",
    response_model=AgentCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_agent(
    payload: AgentCreate,
    db: AsyncSession = Depends(get_db),
):
    try:
        agent, plaintext_key = await registry.create_agent(
            db,
            tenant_id=payload.tenant_id,
            name=payload.name,
            description=payload.description,
            role=payload.role,
            scopes=payload.scopes,
        )
    except registry.RegistryError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return AgentCreateResponse(
        agent=AgentOut.model_validate(agent),
        api_key=plaintext_key,
    )


@router.get("/agents", response_model=list[AgentOut])
async def list_agents(
    tenant_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    return await registry.list_agents(db, tenant_id)


# ─── Auth ───────────────────────────────────────────────────────

@router.post("/agents/token", response_model=AgentTokenResponse)
async def issue_token(
    payload: AgentTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    agent = await registry.authenticate_by_api_key(db, api_key=payload.api_key)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
    token = create_agent_token(
        agent_id=str(agent.id),
        tenant_id=str(agent.tenant_id),
        scopes=agent.scopes,
    )
    return AgentTokenResponse(
        access_token=token,
        expires_in=settings.AGENTSHIELD_ACCESS_TOKEN_MINUTES * 60,
        scopes=agent.scopes,
    )


@router.get("/agents/me", response_model=AgentOut)
async def me(current_agent=Depends(get_current_agent)):
    return current_agent


@router.post("/agents/{agent_id}/suspend", response_model=AgentOut)
async def suspend(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
    _current=Depends(get_current_agent),
):
    try:
        return await registry.suspend_agent(db, agent_id=agent_id)
    except registry.RegistryError as e:
        raise HTTPException(status_code=404, detail=str(e))