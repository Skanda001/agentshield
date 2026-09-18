"""Audit chain HTTP endpoints."""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.chain import get_event_by_id, list_events
from app.audit.export import export_evidence
from app.audit.verifier import verify_chain
from app.core.deps import get_current_agent, get_db
from app.schemas.audit import AuditEventOut, AuditVerificationOut

router = APIRouter(tags=["audit"])


@router.get("/audit/events", response_model=list[AuditEventOut])
async def list_audit_events(
    limit: int = Query(default=100, ge=1, le=1000),
    agent_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    _agent=Depends(get_current_agent),
):
    return await list_events(db, limit=limit, agent_id=agent_id)


@router.get("/audit/events/{event_id}", response_model=AuditEventOut)
async def get_audit_event(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
    _agent=Depends(get_current_agent),
):
    event = await get_event_by_id(db, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Audit event not found")
    return event


@router.get("/audit/verify", response_model=AuditVerificationOut)
async def verify(
    db: AsyncSession = Depends(get_db),
    _agent=Depends(get_current_agent),
):
    return await verify_chain(db)


@router.get("/audit/export")
async def export(
    agent_id: Optional[UUID] = None,
    limit: int = Query(default=500, ge=1, le=5000),
    db: AsyncSession = Depends(get_db),
    _agent=Depends(get_current_agent),
):
    return await export_evidence(db, agent_id=agent_id, limit=limit)