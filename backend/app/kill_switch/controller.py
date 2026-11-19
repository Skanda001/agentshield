"""Kill switch controller.

Precedence: global > tenant > agent > tool.
The first active switch found determines the block reason.
"""
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.kill_switch import KillSwitch


@dataclass
class KillSwitchCheck:
    blocked: bool
    reason: str | None = None
    scope: str | None = None
    kill_switch_id: UUID | None = None


async def _find_active(
    db: AsyncSession,
    *,
    scope: str,
    target_id: str | None,
    tenant_id: UUID | None = None,
) -> KillSwitch | None:
    stmt = select(KillSwitch).where(
        KillSwitch.scope == scope,
        KillSwitch.is_active == True,  # noqa: E712
    )
    if target_id is None:
        stmt = stmt.where(KillSwitch.target_id.is_(None))
    else:
        stmt = stmt.where(KillSwitch.target_id == target_id)

    if tenant_id is not None:
        from sqlalchemy import or_
        stmt = stmt.where(or_(KillSwitch.tenant_id == tenant_id, KillSwitch.tenant_id.is_(None)))

    stmt = stmt.order_by(KillSwitch.activated_at.desc()).limit(1)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def check(
    db: AsyncSession,
    *,
    agent_id: UUID,
    tenant_id: UUID,
    tool: str,
) -> KillSwitchCheck:
    """Return the first active switch in precedence order, if any."""

    # 1. Global
    ks = await _find_active(db, scope="global", target_id=None)
    if ks:
        return KillSwitchCheck(
            blocked=True,
            reason=f"Global kill switch active: {ks.reason}",
            scope="global",
            kill_switch_id=ks.id,
        )

    # 2. Tenant
    ks = await _find_active(db, scope="tenant", target_id=str(tenant_id))
    if ks:
        return KillSwitchCheck(
            blocked=True,
            reason=f"Tenant suspended: {ks.reason}",
            scope="tenant",
            kill_switch_id=ks.id,
        )

    # 3. Agent
    ks = await _find_active(db, scope="agent", target_id=str(agent_id))
    if ks:
        return KillSwitchCheck(
            blocked=True,
            reason=f"Agent suspended: {ks.reason}",
            scope="agent",
            kill_switch_id=ks.id,
        )

    # 4. Tool
    ks = await _find_active(db, scope="tool", target_id=tool, tenant_id=tenant_id)
    if ks:
        return KillSwitchCheck(
            blocked=True,
            reason=f"Tool '{tool}' disabled: {ks.reason}",
            scope="tool",
            kill_switch_id=ks.id,
        )

    return KillSwitchCheck(blocked=False)
