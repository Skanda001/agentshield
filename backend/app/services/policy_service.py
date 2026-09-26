"""Policy service: create policy, add versions, list, evaluate preview."""
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.agent import Agent
from app.db.models.policy import Policy, PolicyVersion
from app.policy_engine.evaluator import EvalContext, EvalResult, evaluate_policy
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


DEFAULT_POLICY_DICT = {
    "name": "enterprise_guardrail_policy",
    "version": 1,
    "description": "Enterprise security guardrail policy for AgentShield",
    "rules": [
        {"name": "allow_order_read", "effect": "allow", "action": "read", "resource": "order", "priority": 10},
        {"name": "allow_customer_read", "effect": "allow", "action": "read", "resource": "customer", "priority": 10},
        {"name": "allow_account_balance", "effect": "allow", "action": "read", "resource": "payment", "priority": 10},
        {"name": "escalate_restricted_customer", "effect": "escalate", "action": "read", "resource": "customer", "conditions": {"data_classification": "restricted"}, "priority": 50},
        {"name": "escalate_restricted_payment", "effect": "escalate", "resource": "payment", "conditions": {"data_classification": "restricted"}, "priority": 70},
        {"name": "escalate_fund_transfer", "effect": "escalate", "action": "transfer", "resource": "payment", "priority": 80},
        {"name": "deny_customer_delete", "effect": "deny", "action": "delete", "resource": "customer", "priority": 100},
        {"name": "deny_offshore_wire", "effect": "deny", "action": "wire", "resource": "payment", "priority": 100},
        {"name": "default_escalate", "effect": "escalate", "priority": 1},
    ]
}


async def ensure_default_policy(db: AsyncSession, tenant_id: UUID) -> Policy:
    """Ensure an active enterprise security policy exists for this tenant, creating or upgrading as needed."""
    from pathlib import Path
    from app.policy_engine.dsl import load_and_validate

    document: Optional[PolicyDocument] = None
    candidates = [
        Path("/app/policies/demo.yaml"),
        Path(__file__).resolve().parent.parent.parent / "policies" / "demo.yaml",
        Path.cwd() / "policies" / "demo.yaml",
        Path("./policies/demo.yaml").resolve(),
    ]
    for c in candidates:
        try:
            if c.exists():
                document = load_and_validate(c)
                break
        except Exception:
            continue

    if not document:
        document = PolicyDocument.model_validate(DEFAULT_POLICY_DICT)

    # Check if a policy already exists for this tenant
    existing = await db.execute(
        select(Policy)
        .where(Policy.tenant_id == tenant_id)
        .order_by(Policy.created_at.desc())
        .limit(1)
    )
    p = existing.scalar_one_or_none()

    if p:
        p.is_active = True
        # Check if the policy has current rules containing escalate_fund_transfer
        curr_doc = await get_current_document(db, p)
        rule_names = [r.name for r in curr_doc.rules] if curr_doc else []
        if "escalate_fund_transfer" not in rule_names:
            await create_policy_version(db, policy=p, document=document)
        else:
            await db.commit()
            await db.refresh(p)
        return p

    # Create new policy
    new_policy = Policy(
        tenant_id=tenant_id,
        name=document.name,
        description=document.description,
        current_version=0,
        is_active=True,
    )
    db.add(new_policy)
    await db.commit()
    await db.refresh(new_policy)

    await create_policy_version(db, policy=new_policy, document=document)
    await db.refresh(new_policy)
    return new_policy


async def find_active_policy_for_tenant(
    db: AsyncSession, tenant_id: UUID
) -> Optional[Policy]:
    """Return the active policy for a tenant, automatically ensuring default security rules if missing."""
    result = await db.execute(
        select(Policy)
        .where(Policy.tenant_id == tenant_id, Policy.is_active == True)  # noqa: E712
        .order_by(Policy.created_at.desc())
        .limit(1)
    )
    pol = result.scalar_one_or_none()
    if pol:
        # Check if current version has up-to-date rules
        curr_doc = await get_current_document(db, pol)
        rule_names = [r.name for r in curr_doc.rules] if curr_doc else []
        if "escalate_fund_transfer" not in rule_names:
            try:
                return await ensure_default_policy(db, tenant_id)
            except Exception:
                pass
        return pol

    # Auto-seed the policy for this tenant
    try:
        return await ensure_default_policy(db, tenant_id)
    except Exception:
        return None


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
) -> EvalResult:
    document = await get_current_document(db, policy)
    if not document:
        # Return a neutral result — callers can treat this as "no match"
        return EvalResult(
            matched_rule=None,
            effect=None,
            reason="Policy has no versions",
            priority=-1,
        )

    ctx = EvalContext(
        agent_name=agent.name,
        role=agent.role,
        action=action,
        resource_type=resource_type,
        arguments=arguments,
        data_classification=data_classification,
    )
    return evaluate_policy(document, ctx)


async def preview_evaluation(
    db: AsyncSession,
    *,
    policy: Policy,
    agent: Agent,
    action: str,
    resource_type: str,
    arguments: dict,
    data_classification: Optional[str] = None,
) -> PolicyEvaluationPreview:
    r = await evaluate_for_agent(
        db,
        policy=policy,
        agent=agent,
        action=action,
        resource_type=resource_type,
        arguments=arguments,
        data_classification=data_classification,
    )
    return PolicyEvaluationPreview(
        matched_rule=r.matched_rule,
        effect=r.effect,
        reason=r.reason,
    )