"""Policy service: create policy, add versions, list, evaluate preview."""
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.agent import Agent
from app.db.models.policy import Policy, PolicyVersion
from app.policy_engine.evaluator import EvalContext, evaluate_policy
from app.policy_engine.versioning import create_policy_version
from app.schemas.policy import PolicyDocument, PolicyEvaluationPreview


class PolicyServiceError(Exception):
    pass


async def create_policy(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    name: str,
    description: Optional[str],
    document: PolicyDocument,
) -> Policy:
    dup = await db.execute(
        select(Policy).where(Policy.tenant_id == tenant_id, Policy.name == name)
    )
    if dup.scalar_one_or_none():
        raise PolicyServiceError(f"Policy '{name}' already exists for this tenant")

    policy = Policy(
        tenant_id=tenant_id,
        name=name,
        description=description,
        current_version=0,
        is_active=True,
    )
    db.add(policy)
    await db.commit()
    await db.refresh(policy)

    await create_policy_version(db, policy=policy, document=document)
    await db.refresh(policy)
    return policy


async def get_policy(db: AsyncSession, policy_id: UUID) -> Optional[Policy]:
    result = await db.execute(select(Policy).where(Policy.id == policy_id))
    return result.scalar_one_or_none()


async def list_policies(db: AsyncSession, tenant_id: UUID) -> list[Policy]:
    result = await db.execute(
        select(Policy)
        .where(Policy.tenant_id == tenant_id)
        .order_by(Policy.created_at.desc())
    )
    return list(result.scalars().all())


async def get_current_document(
    db: AsyncSession, policy: Policy
) -> Optional[PolicyDocument]:
    result = await db.execute(
        select(PolicyVersion)
        .where(PolicyVersion.policy_id == policy.id)
        .order_by(PolicyVersion.version.desc())
        .limit(1)
    )
    v = result.scalar_one_or_none()
    if not v:
        return None
    return PolicyDocument.model_validate(v.document)


async def evaluate_for_agent(
    db: AsyncSession,
    *,
    policy: Policy,
    agent: Agent,
    action: str,
    resource_type: str,
    arguments: dict,
    data_classification: Optional[str] = None,
) -> PolicyEvaluationPreview:
    document = await get_current_document(db, policy)
    if not document:
        return PolicyEvaluationPreview(
            matched_rule=None, effect=None, reason="Policy has no versions"
        )

    ctx = EvalContext(
        agent_name=agent.name,
        role=agent.role,
        action=action,
        resource_type=resource_type,
        arguments=arguments,
        data_classification=data_classification,
    )
    result = evaluate_policy(document, ctx)
    return PolicyEvaluationPreview(
        matched_rule=result.matched_rule,
        effect=result.effect,
        reason=result.reason,
    )