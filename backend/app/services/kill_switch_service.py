"""Kill switch service: activate, deactivate, list."""
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import chain as audit_chain
from app.db.models.agent import Agent
from app.db.models.kill_switch import KillSwitch


class KillSwitchError(Exception):
    pass


async def verify_target_in_tenant(
    db: AsyncSession,
    *,
    scope: str,
    target_id: str,
    tenant_id: UUID,
) -> None:
    """Raise 403 if target_id does not belong to tenant_id for the given scope."""
    if scope == "agent":
        result = await db.execute(
            select(Agent).where(Agent.id == target_id, Agent.tenant_id == tenant_id)
        )
        if not result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="target_id does not belong to your tenant",
            )
    elif scope == "tenant":
        if str(target_id) != str(tenant_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="target_id must match your own tenant_id for scope 'tenant'",
            )
    # scope "tool" uses a tool name string — no DB cross-check needed


async def activate(
    db: AsyncSession,
    *,
    scope: str,
    target_id: str | None,
    reason: str,
    activated_by: str,
    tenant_id: UUID | None = None,
) -> KillSwitch:
    # Idempotence check: if an active switch already exists for this scope+target, reject
    stmt = select(KillSwitch).where(
        KillSwitch.scope == scope,
        KillSwitch.target_id == target_id,
        KillSwitch.is_active == True,  # noqa: E712
    )
    if tenant_id is not None:
        stmt = stmt.where(KillSwitch.tenant_id == tenant_id)
    else:
        stmt = stmt.where(KillSwitch.tenant_id.is_(None))
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()
    if existing:
        raise KillSwitchError(
            f"An active kill switch already exists for scope '{scope}' target '{target_id}'"
        )

    ks = KillSwitch(
        scope=scope,
        target_id=target_id,
        reason=reason,
        activated_by=activated_by,
        is_active=True,
        tenant_id=tenant_id,
    )
    db.add(ks)
    await db.commit()
    await db.refresh(ks)

    await audit_chain.append_event(
        db,
        event_type="kill_switch.activated",
        payload={
            "kill_switch_id": str(ks.id),
            "scope": scope,
            "target_id": target_id,
            "reason": reason,
            "activated_by": activated_by,
            "tenant_id": str(tenant_id) if tenant_id else None,
        },
    )
    return ks


async def deactivate(
    db: AsyncSession,
    *,
    kill_switch_id: UUID,
    deactivated_by: str,
    note: str | None = None,
) -> KillSwitch:
    result = await db.execute(select(KillSwitch).where(KillSwitch.id == kill_switch_id))
    ks = result.scalar_one_or_none()
    if not ks:
        raise KillSwitchError("Kill switch not found")
    if not ks.is_active:
        raise KillSwitchError("Kill switch is not active")

    ks.is_active = False
    ks.deactivated_by = deactivated_by
    ks.deactivated_at = datetime.now(UTC)
    ks.deactivation_note = note

    await db.commit()
    await db.refresh(ks)

    await audit_chain.append_event(
        db,
        event_type="kill_switch.deactivated",
        payload={
            "kill_switch_id": str(ks.id),
            "scope": ks.scope,
            "target_id": ks.target_id,
            "deactivated_by": deactivated_by,
            "note": note,
        },
    )
    return ks


async def list_switches(
    db: AsyncSession,
    *,
    active_only: bool = False,
    scope: str | None = None,
    limit: int = 100,
    tenant_id: UUID | None = None,
) -> list[KillSwitch]:
    stmt = select(KillSwitch).order_by(KillSwitch.activated_at.desc()).limit(max(1, min(limit, 500)))
    if active_only:
        stmt = stmt.where(KillSwitch.is_active == True)  # noqa: E712
    if scope:
        stmt = stmt.where(KillSwitch.scope == scope)
    # Show: global switches (visible to all tenants) + caller's own tenant switches
    if tenant_id:
        from sqlalchemy import or_
        stmt = stmt.where(
            or_(KillSwitch.scope == "global", KillSwitch.tenant_id == tenant_id)
        )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_switch(db: AsyncSession, kill_switch_id: UUID) -> KillSwitch | None:
    result = await db.execute(select(KillSwitch).where(KillSwitch.id == kill_switch_id))
    return result.scalar_one_or_none()
