"""Decision pipeline. Orchestrates the security decision for one tool call.

Chunk 10: check kill switches BEFORE policy evaluation.
If any switch is active, BLOCK immediately with the switch reason.
"""
from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import chain as audit_chain
from app.db.models.agent import Agent
from app.db.models.decision import Decision
from app.gateway.tool_adapter import NormalizedCall, ToolCall, normalize
from app.kill_switch import controller as kill_switch_controller
from app.risk_engine.deterministic import RiskResult, evaluate
from app.risk_engine.signals import extract_signals
from app.schemas.decision import DecideResponse, Signal
from app.services import approval_service, policy_service


@dataclass
class PipelineResult:
    decision: Decision
    response: DecideResponse


async def run(
    db: AsyncSession,
    *,
    agent: Agent,
    call: ToolCall,
    data_classification: str | None = None,
) -> PipelineResult:
    normalized: NormalizedCall = normalize(call)

    sig = extract_signals(
        tool=normalized.tool,
        arguments=normalized.arguments,
        resource_type_explicit=normalized.resource_type,
    )

    # ── 0a. Check HITL Approval (Execution Resume) ───────────
    if normalized.approval_id:
        from datetime import datetime, timezone
        from uuid import UUID as _UUID
        from sqlalchemy import select
        from app.core.crypto import canonical_json, sha256_hex
        from app.db.models.approval import Approval

        rejection_reason = None
        try:
            appr_uuid = _UUID(str(normalized.approval_id))
        except (ValueError, TypeError, AttributeError):
            rejection_reason = "Invalid approval_id format"
            appr_uuid = None

        approved_obj = None
        if appr_uuid:
            # Row lock with_for_update to atomically check and consume the approval
            appr_res = await db.execute(
                select(Approval).where(
                    Approval.id == appr_uuid,
                    Approval.tenant_id == agent.tenant_id,
                ).with_for_update()
            )
            approved_obj = appr_res.scalar_one_or_none()

            if not approved_obj:
                rejection_reason = "Approval not found or belongs to another tenant"
            elif approved_obj.status == "used":
                rejection_reason = "Approval has already been used (single-use constraint)"
            elif approved_obj.status != "approved":
                rejection_reason = f"Approval is not approved (status: {approved_obj.status})"
            elif approved_obj.expires_at <= datetime.now(timezone.utc):
                approved_obj.status = "expired"
                rejection_reason = "Approval has expired"
            else:
                # Bind approval to the exact call it was granted for
                orig_args = approved_obj.request_context.get("arguments", {})
                orig_hash = sha256_hex(canonical_json({"tool": approved_obj.tool, "arguments": orig_args}))
                call_hash = sha256_hex(canonical_json({"tool": normalized.tool, "arguments": normalized.arguments}))
                if approved_obj.tool != normalized.tool or orig_hash != call_hash:
                    rejection_reason = "Approval call arguments or tool mismatch"

        if rejection_reason:
            decision = Decision(
                agent_id=agent.id,
                tenant_id=agent.tenant_id,
                tool=normalized.tool,
                action=sig.action,
                resource_type=sig.resource_type,
                arguments=normalized.arguments,
                verdict="BLOCK",
                risk_score=100.0,
                reasons=[f"Approval rejected: {rejection_reason}"],
                signals=[],
                injection_score=sig.injection_score,
                pii_classification=sig.pii_classification,
                pii_labels=sig.pii_labels,
                note=f"failed_approval_id={normalized.approval_id}",
            )
            db.add(decision)
            await db.flush()
            await audit_chain.append_event(
                db,
                event_type="decision.made",
                payload={
                    "decision_id": str(decision.id),
                    "tool": decision.tool,
                    "verdict": decision.verdict,
                    "risk_score": decision.risk_score,
                    "reasons": decision.reasons,
                    "agent_name": agent.name,
                    "rejection_reason": rejection_reason,
                    "approval_id": str(normalized.approval_id),
                },
                agent_id=agent.id,
                tenant_id=agent.tenant_id,
            )
            await db.commit()
            await db.refresh(decision)
            return PipelineResult(decision=decision, response=_to_response(decision))

        # Successfully authorized — consume the approval atomically (single-use)
        approved_obj.status = "used"
        decision = Decision(
            agent_id=agent.id,
            tenant_id=agent.tenant_id,
            tool=normalized.tool,
            action=sig.action,
            resource_type=sig.resource_type,
            arguments=normalized.arguments,
            verdict="ALLOW",
            risk_score=0.0,
            reasons=[f"Authorized via supervisor sign-off ({approved_obj.decided_by}): {approved_obj.decision_note or 'Manual approval'}"],
            signals=[],
            injection_score=sig.injection_score,
            pii_classification=sig.pii_classification,
            pii_labels=sig.pii_labels,
            note=f"resumed_from_approval={approved_obj.id}",
        )
        db.add(decision)
        await db.flush()
        await audit_chain.append_event(
            db,
            event_type="decision.made",
            payload={
                "decision_id": str(decision.id),
                "tool": decision.tool,
                "verdict": decision.verdict,
                "risk_score": decision.risk_score,
                "reasons": decision.reasons,
                "agent_name": agent.name,
                "resumed_from_approval": str(approved_obj.id),
            },
            agent_id=agent.id,
            tenant_id=agent.tenant_id,
        )
        await db.commit()
        await db.refresh(decision)
        return PipelineResult(
            decision=decision,
            response=_to_response(decision, approval_id=approved_obj.id),
        )

    # ── In-flight PII Masking ────────────────────────────────
    from app.detection.pii.masker import mask_pii_in_data
    masked_args, masked_labels = mask_pii_in_data(normalized.arguments)
    is_masked = bool(masked_labels)

    # ── 0b. Kill switch check (highest precedence) ───────────
    ks = await kill_switch_controller.check(
        db,
        agent_id=agent.id,
        tenant_id=agent.tenant_id,
        tool=normalized.tool,
    )
    if ks.blocked:
        decision = Decision(
            agent_id=agent.id,
            tenant_id=agent.tenant_id,
            tool=normalized.tool,
            action=sig.action,
            resource_type=sig.resource_type,
            arguments=normalized.arguments,
            verdict="BLOCK",
            risk_score=0.0,
            reasons=[ks.reason or "Blocked by kill switch"],
            signals=[],
            injection_score=sig.injection_score,
            pii_classification=sig.pii_classification,
            pii_labels=sig.pii_labels,
            note=f"kill_switch_scope={ks.scope}",
        )
        db.add(decision)
        await db.flush()
        await audit_chain.append_event(
            db,
            event_type="decision.made",
            payload={
                "decision_id": str(decision.id),
                "tool": decision.tool,
                "verdict": decision.verdict,
                "risk_score": decision.risk_score,
                "reasons": decision.reasons,
                "agent_name": agent.name,
            },
            agent_id=agent.id,
            tenant_id=agent.tenant_id,
        )
        await db.commit()
        await db.refresh(decision)
        return PipelineResult(decision=decision, response=_to_response(decision))


    # ── 1. Policy evaluation ─────────────────────────────────
    policy = await policy_service.find_active_policy_for_tenant(db, agent.tenant_id)

    policy_id = None
    policy_rule = None
    policy_effect = None
    policy_reason = None

    if policy:
        eval_result = await policy_service.evaluate_for_agent(
            db,
            policy=policy,
            agent=agent,
            action=sig.action,
            resource_type=sig.resource_type,
            arguments=normalized.arguments,
            data_classification=data_classification or sig.pii_classification,
        )
        if eval_result.matched_rule:
            policy_id = policy.id
            policy_rule = eval_result.matched_rule
            policy_effect = eval_result.effect
            policy_reason = eval_result.reason

    # ── 2. Short-circuit: policy deny ────────────────────────
    if policy_effect == "deny":
        decision = Decision(
            agent_id=agent.id,
            tenant_id=agent.tenant_id,
            tool=normalized.tool,
            action=sig.action,
            resource_type=sig.resource_type,
            arguments=normalized.arguments,
            verdict="BLOCK",
            risk_score=0.0,
            reasons=[f"Denied by policy: {policy_reason}"],
            signals=[],
            policy_id=policy_id,
            policy_rule=policy_rule,
            policy_effect=policy_effect,
            injection_score=sig.injection_score,
            pii_classification=sig.pii_classification,
            pii_labels=sig.pii_labels,
            note=normalized.arguments.get("_reasoning") or normalized.arguments.get("reasoning") or normalized.arguments.get("summary"),
        )
        db.add(decision)
        await db.flush()
        await audit_chain.append_event(
            db,
            event_type="decision.made",
            payload={
                "decision_id": str(decision.id),
                "tool": decision.tool,
                "verdict": decision.verdict,
                "risk_score": decision.risk_score,
                "reasons": decision.reasons,
                "agent_name": agent.name,
            },
            agent_id=agent.id,
            tenant_id=agent.tenant_id,
        )
        await db.commit()
        await db.refresh(decision)
        return PipelineResult(decision=decision, response=_to_response(decision))

    # ── 3. Risk engine ───────────────────────────────────────
    risk: RiskResult = evaluate(
        tool=normalized.tool,
        arguments=normalized.arguments,
        resource_type=normalized.resource_type,
    )

    # ── 4. Combine policy + risk ─────────────────────────────
    if policy_effect == "mask":
        final_verdict = "ALLOW"
        final_reasons = list(risk.reasons) + [f"Sensitive data masked in flight by AgentShield DLP: {policy_reason or 'Protected'}"]
        is_masked = True
    elif policy_effect == "escalate" and risk.verdict == "ALLOW":
        final_verdict = "HITL"
        final_reasons = list(risk.reasons) + [f"Policy escalated (HITL required): {policy_reason}"]
    elif policy_effect == "allow":
        final_verdict = risk.verdict
        final_reasons = list(risk.reasons)
        if policy_reason:
            final_reasons.insert(0, f"Policy allowed: {policy_reason}")
    else:
        final_verdict = risk.verdict
        final_reasons = list(risk.reasons)

    decision = Decision(
        agent_id=agent.id,
        tenant_id=agent.tenant_id,
        tool=normalized.tool,
        action=risk.action,
        resource_type=risk.resource_type,
        arguments=masked_args if is_masked else normalized.arguments,
        verdict=final_verdict,
        risk_score=risk.risk_score,
        reasons=final_reasons,
        signals=[s.model_dump() for s in risk.signals],
        policy_id=policy_id,
        policy_rule=policy_rule,
        policy_effect=policy_effect,
        injection_score=sig.injection_score,
        pii_classification=sig.pii_classification,
        pii_labels=sig.pii_labels,
        note=normalized.arguments.get("_reasoning") or normalized.arguments.get("reasoning") or normalized.arguments.get("summary"),
    )
    db.add(decision)
    await db.flush()   # write decision row; do NOT commit yet

    # Audit event in the SAME transaction — commit once below so
    # decision + audit event are atomic. If audit fails, decision rolls back.
    await audit_chain.append_event(
        db,
        event_type="decision.made",
        payload={
            "decision_id": str(decision.id),
            "tool": decision.tool,
            "action": decision.action,
            "resource_type": decision.resource_type,
            "verdict": decision.verdict,
            "risk_score": decision.risk_score,
            "reasons": decision.reasons,
            "policy_id": str(decision.policy_id) if decision.policy_id else None,
            "policy_rule": decision.policy_rule,
            "policy_effect": decision.policy_effect,
            "injection_score": decision.injection_score,
            "pii_classification": decision.pii_classification,
            "pii_labels": decision.pii_labels,
            "agent_name": agent.name,
            "note": decision.note,
        },
        agent_id=agent.id,
        tenant_id=agent.tenant_id,
    )
    await db.commit()          # ONE commit: decision + audit event together
    await db.refresh(decision)

    # ── 5. Create approval for HITL ──────────────────────────
    approval_id = None
    if final_verdict == "HITL":
        approval = await _create_approval_if_escalated(decision, agent)
        if approval:
            approval_id = approval.id

    return PipelineResult(
        decision=decision,
        response=_to_response(
            decision,
            approval_id=approval_id,
            masked=is_masked,
            masked_arguments=masked_args if is_masked else None,
        ),
    )


async def _create_approval_if_escalated(decision: Decision, agent: Agent) -> Any:
    """Create an approval row and send Slack notification in a separate transaction.

    This runs AFTER the decision has been committed, so a Slack failure
    does not roll back the decision. The approval itself uses its own
    session so it commits independently.
    """
    from app.db.session import AsyncSessionLocal
    from app.hitl.slack_adapter import send_approval_request

    async with AsyncSessionLocal() as db:
        try:
            approval = await approval_service.create_for_decision(
                db, decision=decision, agent=agent
            )
        except approval_service.ApprovalServiceError:
            return None

        from app.core.config import settings
        base = getattr(settings, "APPROVAL_BASE_URL", "http://localhost:8000")
        ok, err = await send_approval_request(
            approval_id=str(approval.id),
            tool=approval.tool,
            agent_name=agent.name,
            risk_score=decision.risk_score,
            reasons=decision.reasons,
            approve_url=f"{base}/api/v1/approvals/{approval.id}/decide",
            deny_url=f"{base}/api/v1/approvals/{approval.id}/decide",
        )

        approval.notified_at = approval.created_at
        approval.notification_channel = "slack" if ok else "none"
        if err:
            approval.notification_error = err[:500]
        await db.commit()
        return approval


def _to_response(
    decision: Decision,
    approval_id: Any = None,
    masked: bool = False,
    masked_arguments: Optional[dict[str, Any]] = None,
) -> DecideResponse:
    return DecideResponse(
        decision_id=decision.id,
        verdict=decision.verdict,
        risk_score=decision.risk_score,
        tool=decision.tool,
        action=decision.action,
        reasons=decision.reasons,
        signals=[Signal(**s) for s in decision.signals] if decision.signals else [],
        policy_id=decision.policy_id,
        policy_rule=decision.policy_rule,
        policy_effect=decision.policy_effect,
        injection_score=decision.injection_score,
        pii_classification=decision.pii_classification,
        pii_labels=decision.pii_labels,
        masked=masked,
        masked_arguments=masked_arguments if masked else None,
        approval_id=approval_id,
        created_at=decision.created_at,
    )