"""Decision pipeline. Orchestrates the security decision for one tool call.

Order (v1):
  normalize -> risk engine -> verdict -> persist -> return

Later chunks insert: policy engine -> injection detection -> audit chain.
The shape stays the same; only the middle grows.
"""
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.agent import Agent
from app.db.models.decision import Decision
from app.gateway.tool_adapter import NormalizedCall, ToolCall, normalize
from app.risk_engine.deterministic import RiskResult, evaluate
from app.schemas.decision import DecideResponse, Signal


@dataclass
class PipelineResult:
    decision: Decision
    response: DecideResponse


async def run(
    db: AsyncSession,
    *,
    agent: Agent,
    call: ToolCall,
) -> PipelineResult:
    normalized: NormalizedCall = normalize(call)

    risk: RiskResult = evaluate(
        tool=normalized.tool,
        arguments=normalized.arguments,
        resource_type=normalized.resource_type,
    )

    note_parts = list(normalized.warnings)
    note = " | ".join(note_parts) if note_parts else None

    decision = Decision(
        agent_id=agent.id,
        tenant_id=agent.tenant_id,
        tool=normalized.tool,
        action=risk.action,
        resource_type=risk.resource_type,
        arguments=normalized.arguments,
        verdict=risk.verdict,
        risk_score=risk.risk_score,
        reasons=risk.reasons,
        signals=[s.model_dump() for s in risk.signals],
        note=note,
    )
    db.add(decision)
    await db.commit()
    await db.refresh(decision)

    response = DecideResponse(
        decision_id=decision.id,
        verdict=decision.verdict,
        risk_score=decision.risk_score,
        tool=decision.tool,
        action=decision.action,
        reasons=decision.reasons,
        signals=[Signal(**s) for s in decision.signals],
        created_at=decision.created_at,
    )
    return PipelineResult(decision=decision, response=response)