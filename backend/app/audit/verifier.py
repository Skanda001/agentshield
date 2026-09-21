"""Audit chain verification.

Walks the chain from the first event to the last, recomputing each hash
and verifying each HMAC signature. Reports the first point of failure.
"""
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.chain import GENESIS_HASH
from app.core.crypto import compute_event_hash, verify_signature
from app.db.models.audit_log import AuditLog


@dataclass
class VerificationResult:
    total_events: int
    verified_events: int
    valid: bool
    broken_at_seq: int | None = None
    reason: str | None = None
    errors: list[str] = field(default_factory=list)


async def verify_chain(
    db: AsyncSession,
    *,
    from_seq: int | None = None,
    to_seq: int | None = None,
) -> VerificationResult:
    """Recompute hashes for every event and verify the chain end-to-end.

    If from_seq is set, we start the walk from that seq and use the
    predecessor's hash as the expected prev_hash. Otherwise we start
    from GENESIS.
    """
    stmt = select(AuditLog).order_by(AuditLog.seq.asc())
    if from_seq is not None:
        stmt = stmt.where(AuditLog.seq >= from_seq)
    if to_seq is not None:
        stmt = stmt.where(AuditLog.seq <= to_seq)

    result = await db.execute(stmt)
    events = list(result.scalars().all())

    if not events:
        return VerificationResult(total_events=0, verified_events=0, valid=True)

    # Determine expected starting prev_hash
    if from_seq is None or from_seq == 1:
        expected_prev = GENESIS_HASH
    else:
        pred = await db.execute(
            select(AuditLog).where(AuditLog.seq < from_seq).order_by(AuditLog.seq.desc()).limit(1)
        )
        pred_row = pred.scalar_one_or_none()
        expected_prev = pred_row.hash if pred_row else GENESIS_HASH

    errors: list[str] = []
    verified = 0

    for event in events:
        if event.prev_hash != expected_prev:
            return VerificationResult(
                total_events=len(events),
                verified_events=verified,
                valid=False,
                broken_at_seq=event.seq,
                reason="prev_hash mismatch",
                errors=errors + [f"seq {event.seq}: prev_hash does not match predecessor"],
            )

        recomputed = compute_event_hash(event.prev_hash, event.payload)
        if recomputed != event.hash:
            return VerificationResult(
                total_events=len(events),
                verified_events=verified,
                valid=False,
                broken_at_seq=event.seq,
                reason="hash mismatch (payload was modified)",
                errors=errors + [f"seq {event.seq}: recomputed hash does not match stored hash"],
            )

        if not verify_signature(event.hash, event.signature):
            return VerificationResult(
                total_events=len(events),
                verified_events=verified,
                valid=False,
                broken_at_seq=event.seq,
                reason="signature invalid (HMAC does not verify)",
                errors=errors + [f"seq {event.seq}: HMAC signature failed"],
            )

        expected_prev = event.hash
        verified += 1

    return VerificationResult(
        total_events=len(events),
        verified_events=verified,
        valid=True,
    )