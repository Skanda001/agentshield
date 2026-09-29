"""Policy HTTP endpoints."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_agent, get_optional_agent, get_db
from app.db.models.policy import Policy, PolicyVersion
from app.policy_engine.dsl import PolicyParseError, load_and_validate
from app.schemas.policy import (
    PolicyCreate,
    PolicyEvaluationPreview,
    PolicyOut,
    PolicySimulateRequest,
    PolicySimulateResponse,
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
    _agent=Depends(get_optional_agent),
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


@router.post("/policies/simulate", response_model=PolicySimulateResponse)
async def simulate_policy(
    payload: PolicySimulateRequest,
    db: AsyncSession = Depends(get_db),
    agent=Depends(get_current_agent),
):
    """Dry-run simulation of a tool call against the active policy and risk engine without DB writes."""
    from app.detection.pii.masker import mask_pii_in_data
    from app.risk_engine.signals import extract_signals
    from app.risk_engine.deterministic import evaluate as evaluate_risk

    # 1. Signals & heuristics
    sig = extract_signals(
        tool=payload.tool,
        arguments=payload.arguments,
        resource_type_explicit=payload.resource_type,
    )

    # 2. In-flight PII Masking preview
    masked_args, masked_labels = mask_pii_in_data(payload.arguments)
    is_masked = bool(masked_labels)

    # 3. Active Policy evaluation
    policy = await svc.find_active_policy_for_tenant(db, agent.tenant_id)
    policy_rule = None
    policy_effect = None
    policy_reason = None

    if policy:
        eval_result = await svc.evaluate_for_agent(
            db,
            policy=policy,
            agent=agent,
            action=sig.action,
            resource_type=sig.resource_type,
            arguments=payload.arguments,
            data_classification=payload.data_classification or sig.pii_classification,
        )
        if eval_result.matched_rule:
            policy_rule = eval_result.matched_rule
            policy_effect = eval_result.effect
            policy_reason = eval_result.reason

    # 4. Risk evaluation
    risk = evaluate_risk(
        tool=payload.tool,
        arguments=payload.arguments,
        resource_type=payload.resource_type,
    )

    # 5. Determine projected verdict
    if policy_effect == "deny":
        verdict = "BLOCK"
        reasons = [f"Denied by policy: {policy_reason}"]
    elif policy_effect == "mask":
        verdict = "ALLOW"
        reasons = list(risk.reasons) + [f"Sensitive data masked in flight by AgentShield DLP: {policy_reason or 'Protected'}"]
        is_masked = True
    elif policy_effect == "escalate" and risk.verdict == "ALLOW":
        verdict = "ESCALATE"
        reasons = list(risk.reasons) + [f"Policy escalated: {policy_reason}"]
    elif policy_effect == "allow":
        verdict = risk.verdict
        reasons = list(risk.reasons)
        if policy_reason:
            reasons.insert(0, f"Policy allowed: {policy_reason}")
    else:
        verdict = risk.verdict
        reasons = list(risk.reasons)

    return PolicySimulateResponse(
        verdict=verdict,
        risk_score=risk.risk_score,
        reasons=reasons,
        matched_rule=policy_rule,
        policy_effect=policy_effect,
        policy_reason=policy_reason,
        action=sig.action,
        resource_type=sig.resource_type,
        signals=[s.model_dump() for s in risk.signals],
        injection_score=sig.injection_score,
        pii_detected=sig.pii_labels,
        masked=is_masked,
        masked_arguments=masked_args if is_masked else None,
    )