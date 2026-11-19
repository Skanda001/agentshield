"""Audit chain verification.

Walks the chain from the first event to the last, recomputing each hash
and verifying each HMAC signature. Reports the first point of failure.

Detects:
- Modified payload (hash mismatch)
- Modified hash or signature (HMAC failure)
- Deleted events (sequence gap)
- Reordered events (prev_hash chain break)
- Cross-tenant isolation (tenant_id filter)
"""
from dataclasses import dataclass, field
from uuid import UUID

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
    tenant_id: UUID | None = None,
    from_seq: int | None = None,
    to_seq: int | None = None,
) -> VerificationResult:
    """Recompute hashes for every event and verify the chain end-to-end.

    Args:
        tenant_id: When set, only verify events for this tenant (scoped verification).
        from_seq:  Start the walk from this seq (inclusive). Defaults to 1.
        to_seq:    End the walk at this seq (inclusive). Defaults to last event.

    Detects:
        - Payload modification (hash mismatch)
        - Hash/signature tampering (HMAC failure)
        - Deleted events (sequence gap — seq values must be consecutive)
        - Reordered events (prev_hash chain break)
    """
    stmt = select(AuditLog).order_by(AuditLog.seq.asc())
    if tenant_id:
        stmt = stmt.where(AuditLog.tenant_id == tenant_id)
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
    prev_seq: int | None = None

    for event in events:
        # ── Gap detection ─────────────────────────────────────────────────
        if prev_seq is not None and event.seq != prev_seq + 1:
            missing = list(range(prev_seq + 1, event.seq))
            return VerificationResult(
                total_events=len(events),
                verified_events=verified,
                valid=False,
                broken_at_seq=event.seq,
                reason=f"sequence gap: missing seq(s) {missing}",
                errors=errors + [f"Gap detected: seq {prev_seq} → {event.seq}, missing {missing}"],
            )

        # ── prev_hash chain check (detects reorder) ───────────────────────
        if event.prev_hash != expected_prev:
            return VerificationResult(
                total_events=len(events),
                verified_events=verified,
                valid=False,
                broken_at_seq=event.seq,
                reason="prev_hash mismatch (deleted or reordered event)",
                errors=errors + [f"seq {event.seq}: prev_hash does not match predecessor"],
            )

        # ── Payload hash recomputation ────────────────────────────────────
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

        # ── HMAC signature check ──────────────────────────────────────────
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
        prev_seq = event.seq
        verified += 1

    return VerificationResult(
        total_events=len(events),
        verified_events=verified,
        valid=True,
    )
