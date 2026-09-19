"""Integration test: the audit chain detects tampering.

Verifies linkage, clean verification of our slice, and detection after a
direct payload modification. Does not assume anything about the sequence's
current value — works on any DB state.

Set RUN_INTEGRATION_TESTS=1 to enable.
"""
import os

import pytest
from sqlalchemy import delete

from app.audit import chain as audit_chain
from app.audit.verifier import verify_chain
from app.db.models.audit_log import AuditLog
from app.db.session import AsyncSessionLocal


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION_TESTS") != "1",
    reason="set RUN_INTEGRATION_TESTS=1 to run integration tests against the live DB",
)


@pytest.mark.asyncio
async def test_audit_chain_detects_tampering():
    async with AsyncSessionLocal() as db:
        # Append two events — no assumptions about sequence values
        e1 = await audit_chain.append_event(
            db, event_type="test.tamper.first", payload={"n": 1}
        )
        e2 = await audit_chain.append_event(
            db, event_type="test.tamper.second", payload={"n": 2}
        )

        # Linkage
        assert e2.prev_hash == e1.hash
        assert e2.seq == e1.seq + 1

        # Verify our slice cleanly
        result = await verify_chain(db, from_seq=e1.seq)
        assert result.valid is True, f"chain should be valid: {result}"

        # Tamper e1's payload in place
        e1.payload = {**e1.payload, "payload": {"n": 999}}
        await db.commit()

        # Re-verify — must detect
        result = await verify_chain(db, from_seq=e1.seq)
        assert result.valid is False
        assert result.broken_at_seq == e1.seq
        assert result.reason is not None
        assert "hash mismatch" in result.reason.lower()

        # Cleanup
        await db.execute(delete(AuditLog).where(AuditLog.seq >= e1.seq))
        await db.commit()