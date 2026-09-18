"""Policy HTTP endpoints."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_agent, get_db
from app.db.models.policy import Policy, PolicyVersion
from app.policy_engine.dsl import PolicyParseError, load_and_validate
from app.schemas.policy import (
    PolicyCreate,
    PolicyEvaluationPreview,
    PolicyOut,
    PolicyVersionOut,
)
from app.services import policy_service as svc

router = APIRouter(tags=["policies"])


@router.post("/policies", response_model=PolicyOut, status_code=status.HTTP_201_CREATED)
async def create_policy(
    payload: PolicyCreate,
    db: AsyncSession = Depends(get_db),
    _agent=Depends(get_current_agent),
):
    try:
        policy = await svc.create_policy(
            db,
            tenant_id=payload.tenant_id,
            name=payload.name,
            description=payload.description,
            document=payload.document,
        )
    except svc.PolicyServiceError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return policy


@router.get("/policies", response_model=list[PolicyOut])
async def list_policies(
    tenant_id: UUID,
    db: AsyncSession = Depends(get_db),
    _agent=Depends(get_current_agent),
):
    return await svc.list_policies(db, tenant_id)


@router.post("/policies/load-yaml", response_model=PolicyOut)
async def load_policy_from_yaml(
    tenant_id: UUID,
    file_path: str,
    db: AsyncSession = Depends(get_db),
    _agent=Depends(get_current_agent),
):
    try:
        document = load_and_validate(file_path)
    except PolicyParseError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        policy = await svc.create_policy(
            db,
            tenant_id=tenant_id,
            name=document.name,
            description=document.description,
            document=document,
        )
    except svc.PolicyServiceError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return policy


@router.get("/policies/{policy_id}/versions", response_model=list[PolicyVersionOut])
async def list_versions(
    policy_id: UUID,
    db: AsyncSession = Depends(get_db),
    _agent=Depends(get_current_agent),
):
    from app.policy_engine.versioning import list_versions as list_v
    return await list_v(db, policy_id)


@router.post("/policies/{policy_id}/evaluate", response_model=PolicyEvaluationPreview)
async def evaluate(
    policy_id: UUID,
    action: str,
    resource_type: str,
    data_classification: str | None = None,
    db: AsyncSession = Depends(get_db),
    agent=Depends(get_current_agent),
):
    policy = await svc.get_policy(db, policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    return await svc.preview_evaluation(
        db,
        policy=policy,
        agent=agent,
        action=action,
        resource_type=resource_type,
        arguments={},
        data_classification=data_classification,
    )