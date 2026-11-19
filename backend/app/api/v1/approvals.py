"""Approval HTTP endpoints."""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_agent, get_db
from app.schemas.approval import ApprovalDecision, ApprovalOut
from app.services import approval_service as svc

router = APIRouter(tags=["approvals"])


@router.get("/approvals", response_model=list[ApprovalOut])
async def list_approvals(
    status: Optional[str] = Query(default=None, pattern=r"^(pending|approved|denied|expired)$"),
    limit: int = Query(default=50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    agent=Depends(get_current_agent),
):
    """List approvals scoped to the caller's tenant."""
    return await svc.list_approvals(
        db, tenant_id=agent.tenant_id, status=status, limit=limit
    )


@router.get("/approvals/{approval_id}", response_model=ApprovalOut)
async def get_approval(
    approval_id: UUID,
    db: AsyncSession = Depends(get_db),
    agent=Depends(get_current_agent),
):
    approval = await svc.get_approval(db, approval_id)
    if not approval or str(approval.tenant_id) != str(agent.tenant_id):
        raise HTTPException(status_code=404, detail="Approval not found")
    return approval


@router.post("/approvals/{approval_id}/decide", response_model=ApprovalOut)
async def decide(
    approval_id: UUID,
    payload: ApprovalDecision,
    db: AsyncSession = Depends(get_db),
    agent=Depends(get_current_agent),
):
    approval = await svc.get_approval(db, approval_id)

    # 404 for missing OR cross-tenant (don't leak existence to other tenants)
    if not approval or str(approval.tenant_id) != str(agent.tenant_id):
        raise HTTPException(status_code=404, detail="Approval not found")

    # Separation of duties: the requesting agent cannot approve its own request
    if str(approval.agent_id) == str(agent.id):
        raise HTTPException(
            status_code=403,
            detail="Agents may not approve their own requests (separation of duties)",
        )

    # decided_by always comes from the authenticated principal — never from the request body
    decided_by = agent.name or str(agent.id)

    try:
        return await svc.decide(
            db,
            approval=approval,
            approved=payload.approved,
            decided_by=decided_by,
            note=payload.note,
        )
    except svc.ApprovalServiceError as e:
        raise HTTPException(status_code=400, detail=str(e))