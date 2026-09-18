"""Audit chain: append events with hash chaining + HMAC signature.

Guarantees:
- Every event links to its predecessor via prev_hash
- Every event's hash covers (prev_hash, canonical payload)
- Every hash is HMAC-signed so tampering is detectable even if an
  attacker has write access to the DB but not to AUDIT_HMAC_SECRET
- A monotonic sequence number gives total order
- The append is serialized with a Postgres advisory lock so concurrent
  writers cannot fork the chain.
"""
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import (
    canonical_json,
    compute_event_hash,
    sign_hash,
)
from app.db.models.audit_log import AuditLog


GENESIS_HASH = "0" * 64
ADVISORY_LOCK_KEY = 84_041_018   # arbitrary but fixed


async def _get_tail(db: AsyncSession) -> AuditLog | None:
    result = await db.execute(
        select(AuditLog).order_by(AuditLog.seq.desc()).limit(1)
    )
    return result.scalar_one_or_none()


async def append_event(
    db: AsyncSession,
    *,
    event_type: str,
    payload: dict[str, Any],
    agent_id: Optional[UUID] = None,
    tenant_id: Optional[UUID] = None,
    note: Optional[str] = None,
) -> AuditLog:
    """Append one event to the chain. Serializes concurrent writers."""
    # Serialize all appends with a transaction-scoped advisory lock.
    await db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": ADVISORY_LOCK_KEY})

    tail = await _get_tail(db)
    prev_hash = tail.hash if tail else GENESIS_HASH

    # Canonical, timestamped payload
    ts = datetime.now(timezone.utc).isoformat()
    full_payload = {
        "event_type": event_type,
        "payload": payload,
        "agent_id": str(agent_id) if agent_id else None,
        "tenant_id": str(tenant_id) if tenant_id else None,
        "timestamp": ts,
    }

    chain_hash = compute_event_hash(prev_hash, full_payload)
    signature = sign_hash(chain_hash)

    event = AuditLog(
        event_type=event_type,
        agent_id=agent_id,
        tenant_id=tenant_id,
        payload=full_payload,
        prev_hash=prev_hash,
        hash=chain_hash,
        signature=signature,
        note=note,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event


async def list_events(
    db: AsyncSession,
    *,
    limit: int = 100,
    agent_id: Optional[UUID] = None,
) -> list[AuditLog]:
    stmt = select(AuditLog).order_by(AuditLog.seq.desc()).limit(max(1, min(limit, 1000)))
    if agent_id:
        stmt = stmt.where(AuditLog.agent_id == agent_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_event_by_id(db: AsyncSession, event_id: UUID) -> AuditLog | None:
    result = await db.execute(select(AuditLog).where(AuditLog.id == event_id))
    return result.scalar_one_or_none()


async def get_by_seq(db: AsyncSession, seq: int) -> AuditLog | None:
    result = await db.execute(select(AuditLog).where(AuditLog.seq == seq))
    return result.scalar_one_or_none()