"""Export an audit slice as a JSON evidence pack.

Includes the events plus a manifest with integrity metadata so an
external party can independently verify the chain later.
"""
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.chain import list_events
from app.audit.verifier import verify_chain


async def export_evidence(
    db: AsyncSession,
    *,
    agent_id: Optional[UUID] = None,
    limit: int = 500,
) -> dict[str, Any]:
    events = await list_events(db, limit=limit, agent_id=agent_id)

    verification = await verify_chain(db)

    return {
        "manifest": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "agent_id_filter": str(agent_id) if agent_id else None,
            "event_count": len(events),
            "chain_valid": verification.valid,
            "verified_events": verification.verified_events,
        },
        "events": [
            {
                "seq": e.seq,
                "id": str(e.id),
                "event_type": e.event_type,
                "agent_id": str(e.agent_id) if e.agent_id else None,
                "tenant_id": str(e.tenant_id) if e.tenant_id else None,
                "payload": e.payload,
                "prev_hash": e.prev_hash,
                "hash": e.hash,
                "signature": e.signature,
                "created_at": e.created_at.isoformat(),
            }
            for e in events
        ],
    }