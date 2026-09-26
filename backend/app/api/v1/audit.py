"""Audit chain HTTP endpoints."""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.chain import get_event_by_id, list_events
from app.audit.export import export_evidence
from app.audit.verifier import verify_chain
from app.core.deps import get_current_agent, get_db, get_optional_agent
from app.schemas.audit import AuditEventOut, AuditVerificationOut

router = APIRouter(tags=["audit"])


@router.get("/audit/events", response_model=list[AuditEventOut])
async def list_audit_events(
    limit: int = Query(default=100, ge=1, le=1000),
    agent_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    _agent=Depends(get_optional_agent),
):
    return await list_events(db, limit=limit, agent_id=agent_id)


@router.get("/audit/events/{event_id}", response_model=AuditEventOut)
async def get_audit_event(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
    _agent=Depends(get_optional_agent),
):
    event = await get_event_by_id(db, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Audit event not found")
    return event


@router.get("/audit/verify", response_model=AuditVerificationOut)
async def verify(
    db: AsyncSession = Depends(get_db),
    _agent=Depends(get_optional_agent),
):
    return await verify_chain(db)


@router.get("/audit/export")
async def export(
    agent_id: Optional[UUID] = None,
    limit: int = Query(default=500, ge=1, le=5000),
    db: AsyncSession = Depends(get_db),
    _agent=Depends(get_optional_agent),
):
    return await export_evidence(db, agent_id=agent_id, limit=limit)


from datetime import datetime
from typing import Any
from pydantic import BaseModel
from sqlalchemy import desc, select
from app.db.models.decision import Decision


class CallLogItem(BaseModel):
    id: UUID
    created_at: datetime
    tool: str
    verdict: str
    reasons: list[str]
    primary_reason: str
    risk_score: float
    arguments: dict[str, Any]
    agent_id: UUID
    policy_rule: Optional[str] = None
    policy_effect: Optional[str] = None
    data_classification: Optional[str] = None


@router.get("/audit/logs", response_model=list[CallLogItem])
async def list_audit_logs(
    verdict: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _agent=Depends(get_optional_agent),
):
    """Retrieve structured audit call logs with verdict, reasons, risk score, and parameters."""
    stmt = select(Decision).order_by(desc(Decision.created_at))
    if verdict and verdict.upper() != "ALL":
        if verdict.upper() in ("ESCALATE", "HITL"):
            stmt = stmt.where(Decision.verdict.in_(["ESCALATE", "HITL"]))
        else:
            stmt = stmt.where(Decision.verdict == verdict.upper())
    stmt = stmt.limit(limit)
    result = await db.execute(stmt)
    decisions = list(result.scalars().all())

    items = []
    for d in decisions:
        reasons = d.reasons or []
        primary = reasons[0] if reasons else ("Safe execution permitted" if d.verdict == "ALLOW" else "Policy enforcement")
        items.append(
            CallLogItem(
                id=d.id,
                created_at=d.created_at,
                tool=d.tool,
                verdict=d.verdict,
                reasons=reasons,
                primary_reason=primary,
                risk_score=d.risk_score,
                arguments=d.arguments or {},
                agent_id=d.agent_id,
                policy_rule=d.policy_rule,
                policy_effect=d.policy_effect,
                data_classification=d.pii_classification,
            )
        )
    return items