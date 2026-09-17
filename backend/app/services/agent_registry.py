"""Business logic for tenants and agents."""
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import generate_api_key, hash_api_key
from app.db.models.agent import Agent
from app.db.models.tenant import Tenant


class RegistryError(Exception):
    """Raised for domain-level failures (not found, duplicate, etc.)."""


# ─── Tenants ───────────────────────────────────────────────────

async def create_tenant(
    db: AsyncSession, *, name: str, slug: str
) -> Tenant:
    existing = await db.execute(select(Tenant).where(Tenant.slug == slug))
    if existing.scalar_one_or_none():
        raise RegistryError(f"Tenant with slug '{slug}' already exists")

    tenant = Tenant(name=name, slug=slug)
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)
    return tenant


async def get_tenant(db: AsyncSession, tenant_id: UUID) -> Optional[Tenant]:
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    return result.scalar_one_or_none()


# ─── Agents ────────────────────────────────────────────────────

async def create_agent(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    name: str,
    description: Optional[str],
    role: str,
    scopes: list[str],
) -> tuple[Agent, str]:
    """Create an agent. Returns (agent, plaintext_api_key).

    The plaintext key is returned exactly once and never stored.
    Only the HMAC-SHA256 hash is persisted.
    """
    tenant = await get_tenant(db, tenant_id)
    if not tenant:
        raise RegistryError(f"Tenant {tenant_id} not found")
    if not tenant.is_active:
        raise RegistryError("Tenant is inactive")

    # Uniqueness check for (tenant_id, name)
    dup = await db.execute(
        select(Agent).where(Agent.tenant_id == tenant_id, Agent.name == name)
    )
    if dup.scalar_one_or_none():
        raise RegistryError(f"Agent '{name}' already exists in this tenant")

    plaintext_key = generate_api_key()
    agent = Agent(
        tenant_id=tenant_id,
        name=name,
        description=description,
        api_key_hash=hash_api_key(plaintext_key),
        scopes=scopes,
        role=role,
        status="active",
        is_active=True,
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent, plaintext_key


async def list_agents(db: AsyncSession, tenant_id: UUID) -> list[Agent]:
    result = await db.execute(
        select(Agent).where(Agent.tenant_id == tenant_id).order_by(Agent.created_at.desc())
    )
    return list(result.scalars().all())


async def authenticate_by_api_key(
    db: AsyncSession, *, api_key: str
) -> Optional[Agent]:
    """Look up an agent by its hashed API key. Returns None if no match."""
    hashed = hash_api_key(api_key)
    result = await db.execute(select(Agent).where(Agent.api_key_hash == hashed))
    agent = result.scalar_one_or_none()
    if not agent:
        return None
    if agent.status != "active" or not agent.is_active:
        return None
    return agent


async def suspend_agent(db: AsyncSession, *, agent_id: UUID) -> Agent:
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise RegistryError(f"Agent {agent_id} not found")
    agent.status = "suspended"
    agent.is_active = False
    await db.commit()
    await db.refresh(agent)
    return agent