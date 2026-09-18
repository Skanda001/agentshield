"""Kill switch service: activate, deactivate, list."""
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import chain as audit_chain
from app.db.models.kill_switch import KillSwitch


class KillSwitchError(Exception):
    pass


async def activate(
    db: AsyncSession,
    *,
    scope: str,
    target_id: Optional[str],
    reason: str,
    activated_by: str,
) -> KillSwitch:
    # Idempotence check: if an active switch already exists for this scope+target, reject
    stmt = select(KillSwitch).where(
        KillSwitch.scope == scope,
        KillSwitch.target_id == target_id,
        KillSwitch.is_active == True,  # noqa: E712
    )
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
        },
    )
    return ks


async def deactivate(
    db: AsyncSession,
    *,
    kill_switch_id: UUID,
    deactivated_by: str,
    note: Optional[str] = None,
) -> KillSwitch:
    result = await db.execute(select(KillSwitch).where(KillSwitch.id == kill_switch_id))
    ks = result.scalar_one_or_none()
    if not ks:
        raise KillSwitchError("Kill switch not found")
    if not ks.is_active:
        raise KillSwitchError("Kill switch is not active")

    ks.is_active = False
    ks.deactivated_by = deactivated_by
    ks.deactivated_at = datetime.now(timezone.utc)
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
    scope: Optional[str] = None,
    limit: int = 100,
) -> list[KillSwitch]:
    stmt = select(KillSwitch).order_by(KillSwitch.activated_at.desc()).limit(max(1, min(limit, 500)))
    if active_only:
        stmt = stmt.where(KillSwitch.is_active == True)  # noqa: E712
    if scope:
        stmt = stmt.where(KillSwitch.scope == scope)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_switch(db: AsyncSession, kill_switch_id: UUID) -> Optional[KillSwitch]:
    result = await db.execute(select(KillSwitch).where(KillSwitch.id == kill_switch_id))
    return result.scalar_one_or_none()